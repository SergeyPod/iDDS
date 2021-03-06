#!/usr/bin/env python
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0OA
#
# Authors:
# - Wen Guan, <wen.guan@cern.ch>, 2019 - 2020


"""
operations related to Processings.
"""

import datetime

import sqlalchemy
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.sql.expression import asc

from idds.common import exceptions
from idds.common.constants import ProcessingStatus, ProcessingLocking, GranularityType
from idds.orm.base.session import read_session, transactional_session
from idds.orm.base import models


def create_processing(transform_id, status=ProcessingStatus.New, locking=ProcessingLocking.Idle, submitter=None,
                      granularity=None, granularity_type=GranularityType.File, expired_at=None, processing_metadata=None,
                      substatus=ProcessingStatus.New, output_metadata=None):
    """
    Create a processing.

    :param transform_id: Transform id.
    :param status: processing status.
    :param locking: processing locking.
    :param submitter: submitter name.
    :param granularity: Granularity size.
    :param granularity_type: Granularity type.
    :param expired_at: The datetime when it expires.
    :param processing_metadata: The metadata as json.

    :returns: processing.
    """
    new_processing = models.Processing(transform_id=transform_id, status=status, substatus=substatus, locking=locking,
                                       submitter=submitter, granularity=granularity, granularity_type=granularity_type,
                                       expired_at=expired_at, processing_metadata=processing_metadata,
                                       output_metadata=output_metadata)
    return new_processing


@transactional_session
def add_processing(transform_id, status=ProcessingStatus.New, locking=ProcessingLocking.Idle, submitter=None,
                   granularity=None, granularity_type=GranularityType.File, expired_at=None, processing_metadata=None,
                   output_metadata=None, session=None):
    """
    Add a processing.

    :param transform_id: Transform id.
    :param status: processing status.
    :param locking: processing locking.
    :param submitter: submitter name.
    :param granularity: Granularity size.
    :param granularity_type: Granularity type.
    :param expired_at: The datetime when it expires.
    :param processing_metadata: The metadata as json.

    :raises DuplicatedObject: If a processing with the same name exists.
    :raises DatabaseException: If there is a database error.

    :returns: processing id.
    """
    try:
        new_processing = create_processing(transform_id=transform_id, status=status, locking=locking, submitter=submitter,
                                           granularity=granularity, granularity_type=granularity_type, expired_at=expired_at,
                                           processing_metadata=processing_metadata, output_metadata=output_metadata)
        new_processing.save(session=session)
        proc_id = new_processing.processing_id
        return proc_id
    except IntegrityError as error:
        raise exceptions.DuplicatedObject('Processing already exists!: %s' % (error))
    except DatabaseError as error:
        raise exceptions.DatabaseException(error)


@read_session
def get_processing(processing_id, to_json=False, session=None):
    """
    Get processing or raise a NoObject exception.

    :param processing_id: Processing id.
    :param to_json: return json format.

    :param session: The database session in use.

    :raises NoObject: If no processing is founded.

    :returns: Processing.
    """

    try:
        query = session.query(models.Processing)\
                       .filter_by(processing_id=processing_id)
        ret = query.first()
        if not ret:
            return None
        else:
            if to_json:
                return ret.to_dict_json()
            else:
                return ret.to_dict()
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Processing(processing_id: %s) cannot be found: %s' %
                                  (processing_id, error))
    except Exception as error:
        raise error


@read_session
def get_processings_by_transform_id(transform_id=None, to_json=False, session=None):
    """
    Get processings or raise a NoObject exception.

    :param tranform_id: Transform id.
    :param session: The database session in use.

    :raises NoObject: If no processing is founded.

    :returns: Processings.
    """

    try:
        query = session.query(models.Processing)\
                       .filter_by(transform_id=transform_id)
        query = query.order_by(asc(models.Processing.processing_id))

        ret = query.all()
        if not ret:
            return []
        else:
            items = []
            for t in ret:
                if to_json:
                    items.append(t.to_dict_json())
                else:
                    items.append(t.to_dict())
            return items
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Processings(transform_id: %s) cannot be found: %s' %
                                  (transform_id, error))
    except Exception as error:
        raise error


@read_session
def get_processings_by_status(status, period=None, locking=False, bulk_size=None, submitter=None, to_json=False, session=None):
    """
    Get processing or raise a NoObject exception.

    :param status: Processing status of list of processing status.
    :param period: Time period in seconds.
    :param locking: Whether to retrieve only unlocked items.
    :param bulk_size: bulk size limitation.
    :param submitter: The submitter name.
    :param to_json: return json format.

    :param session: The database session in use.

    :raises NoObject: If no processing is founded.

    :returns: Processings.
    """

    try:
        if not isinstance(status, (list, tuple)):
            status = [status]
        if len(status) == 1:
            status = [status[0], status[0]]

        query = session.query(models.Processing)\
                       .filter(models.Processing.status.in_(status))\
                       .filter(models.Processing.next_poll_at < datetime.datetime.utcnow())

        if period:
            query = query.filter(models.Processing.updated_at < datetime.datetime.utcnow() - datetime.timedelta(seconds=period))
        if locking:
            query = query.filter(models.Processing.locking == ProcessingLocking.Idle)
        if submitter:
            query = query.filter(models.Processing.submitter == submitter)

        query = query.order_by(asc(models.Processing.updated_at))

        if bulk_size:
            query = query.limit(bulk_size)

        tmp = query.all()
        rets = []
        if tmp:
            for t in tmp:
                if to_json:
                    rets.append(t.to_dict_json())
                else:
                    rets.append(t.to_dict())
        return rets
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('No processing attached with status (%s): %s' % (status, error))
    except Exception as error:
        raise error


@transactional_session
def update_processing(processing_id, parameters, session=None):
    """
    update a processing.

    :param processing_id: the transform id.
    :param parameters: A dictionary of parameters.
    :param session: The database session in use.

    :raises NoObject: If no content is founded.
    :raises DatabaseException: If there is a database error.

    """
    try:

        parameters['updated_at'] = datetime.datetime.utcnow()
        if 'status' in parameters and parameters['status'] in [ProcessingStatus.Finished, ProcessingStatus.Failed,
                                                               ProcessingStatus.Lost]:
            parameters['finished_at'] = datetime.datetime.utcnow()

        session.query(models.Processing).filter_by(processing_id=processing_id)\
               .update(parameters, synchronize_session=False)
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Processing %s cannot be found: %s' % (processing_id, error))


@transactional_session
def delete_processing(processing_id=None, session=None):
    """
    delete a processing.

    :param processing_id: The id of the processing.
    :param session: The database session in use.

    :raises NoObject: If no processing is founded.
    :raises DatabaseException: If there is a database error.
    """
    try:
        session.query(models.Processing).filter_by(processing_id=processing_id).delete()
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Processing %s cannot be found: %s' % (processing_id, error))


@transactional_session
def clean_locking(time_period=3600, session=None):
    """
    Clearn locking which is older than time period.

    :param time_period in seconds
    """
    params = {'locking': 0}
    session.query(models.Processing).filter(models.Processing.locking == ProcessingLocking.Locking)\
           .filter(models.Processing.updated_at < datetime.datetime.utcnow() - datetime.timedelta(seconds=time_period))\
           .update(params, synchronize_session=False)


@transactional_session
def clean_next_poll_at(status, session=None):
    """
    Clearn next_poll_at.

    :param status: status of the processing
    """
    if not isinstance(status, (list, tuple)):
        status = [status]
    if len(status) == 1:
        status = [status[0], status[0]]

    params = {'next_poll_at': datetime.datetime.utcnow()}
    session.query(models.Processing).filter(models.Processing.status.in_(status))\
           .update(params, synchronize_session=False)
