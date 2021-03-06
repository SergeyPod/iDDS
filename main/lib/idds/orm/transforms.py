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
operations related to Transform.
"""

import datetime

import sqlalchemy
from sqlalchemy import and_
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.sql.expression import asc, desc

from idds.common import exceptions
from idds.common.constants import TransformStatus, TransformLocking, CollectionRelationType
from idds.orm.base.session import read_session, transactional_session
from idds.orm.base import models


def create_transform(transform_type, transform_tag=None, priority=0, status=TransformStatus.New, locking=TransformLocking.Idle,
                     retries=0, expired_at=None, transform_metadata=None):
    """
    Create a transform.

    :param transform_type: Transform type.
    :param transform_tag: Transform tag.
    :param priority: priority.
    :param status: Transform status.
    :param locking: Transform locking.
    :param retries: The number of retries.
    :param expired_at: The datetime when it expires.
    :param transform_metadata: The metadata as json.

    :returns: transform.
    """
    new_transform = models.Transform(transform_type=transform_type, transform_tag=transform_tag, priority=priority,
                                     status=status, locking=locking, retries=retries, expired_at=expired_at,
                                     transform_metadata=transform_metadata)
    return new_transform


@transactional_session
def add_transform(transform_type, transform_tag=None, priority=0, status=TransformStatus.New, locking=TransformLocking.Idle,
                  retries=0, expired_at=None, transform_metadata=None, workprogress_id=None, session=None):
    """
    Add a transform.

    :param transform_type: Transform type.
    :param transform_tag: Transform tag.
    :param priority: priority.
    :param status: Transform status.
    :param locking: Transform locking.
    :param retries: The number of retries.
    :param expired_at: The datetime when it expires.
    :param transform_metadata: The metadata as json.

    :raises DuplicatedObject: If a transform with the same name exists.
    :raises DatabaseException: If there is a database error.

    :returns: transform id.
    """
    try:
        new_transform = create_transform(transform_type=transform_type, transform_tag=transform_tag, priority=priority,
                                         status=status, locking=locking, retries=retries, expired_at=expired_at,
                                         transform_metadata=transform_metadata)
        new_transform.save(session=session)
        transform_id = new_transform.transform_id

        if workprogress_id:
            new_wp2transform = models.Workprogress2transform(workprogress_id=workprogress_id, transform_id=transform_id)
            new_wp2transform.save(session=session)

        return transform_id
    except IntegrityError as error:
        raise exceptions.DuplicatedObject('Transform already exists!: %s' % (error))
    except DatabaseError as error:
        raise exceptions.DatabaseException(error)


@transactional_session
def add_req2transform(request_id, transform_id, session=None):
    """
    Add the relation between request_id and transform_id

    :param request_id: Request id.
    :param transform_id: Transform id.
    :param session: The database session in use.
    """
    try:
        new_req2transform = models.Req2transform(request_id=request_id, transform_id=transform_id)
        new_req2transform.save(session=session)
    except IntegrityError as error:
        raise exceptions.DuplicatedObject('Request2Transform already exists!(%s:%s): %s' %
                                          (request_id, transform_id, error))
    except DatabaseError as error:
        raise exceptions.DatabaseException(error)


@transactional_session
def add_wp2transform(workprogress_id, transform_id, session=None):
    """
    Add the relation between workprogress_id and transform_id

    :param workprogress_id: Workprogress id.
    :param transform_id: Transform id.
    :param session: The database session in use.
    """
    try:
        new_wp2transform = models.Workprogress2transform(workprogress_id=workprogress_id, transform_id=transform_id)
        new_wp2transform.save(session=session)
    except IntegrityError as error:
        raise exceptions.DuplicatedObject('Workprogress2Transform already exists!(%s:%s): %s' %
                                          (workprogress_id, transform_id, error))
    except DatabaseError as error:
        raise exceptions.DatabaseException(error)


@read_session
def get_transform(transform_id, to_json=False, session=None):
    """
    Get transform or raise a NoObject exception.

    :param transform_id: Transform id.
    :param session: The database session in use.

    :raises NoObject: If no transform is founded.

    :returns: Transform.
    """

    try:
        query = session.query(models.Transform)\
                       .filter(models.Transform.transform_id == transform_id)
        ret = query.first()
        if not ret:
            return None
        else:
            if to_json:
                return ret.to_dict_json()
            else:
                return ret.to_dict()
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Transform(transform_id: %s) cannot be found: %s' %
                                  (transform_id, error))
    except Exception as error:
        raise error


@read_session
def get_transforms_with_input_collection(transform_type, transform_tag, coll_scope, coll_name, to_json=False, session=None):
    """
    Get transforms or raise a NoObject exception.

    :param transform_type: Transform type.
    :param transform_tag: Transform tag.
    :param coll_scope: The collection scope.
    :param coll_name: The collection name.
    :param to_json: return json format.

    :param session: The database session in use.

    :raises NoObject: If no transform is founded.

    :returns: Transform.
    """

    try:
        subquery = session.query(models.Collection.transform_id)\
                          .filter(models.Collection.scope == coll_scope)\
                          .filter(models.Collection.name == coll_name)\
                          .filter(models.Collection.relation_type == CollectionRelationType.Input)\
                          .subquery()
        query = session.query(models.Transform)\
                       .join(subquery, and_(subquery.c.transform_id == models.Transform.transform_id,
                                            models.Transform.transform_type == transform_type,
                                            models.Transform.transform_tag == transform_tag))
        tmp = query.all()
        rets = []
        if tmp:
            for transf in tmp:
                if to_json:
                    rets.append(transf.to_dict_json())
                else:
                    rets.append(transf.to_dict())
        return rets
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Transform(transform_type: %s, transform_tag: %s, coll_scope: %s, coll_name: %s) cannot be found: %s' %
                                  (transform_type, transform_tag, coll_scope, coll_name, error))
    except Exception as error:
        raise error


@read_session
def get_transform_ids(workprogress_id=None, request_id=None, workload_id=None, transform_id=None, session=None):
    """
    Get transform ids or raise a NoObject exception.

    :param workprogress_id: Workprogress id.
    :param workload_id: Workload id.
    :param transform_id: Transform id.
    :param session: The database session in use.

    :raises NoObject: If no transform is founded.

    :returns: list of transform ids.
    """
    try:
        if workload_id:
            query = session.query(models.Req2transform.transform_id)\
                           .join(models.Request, and_(models.Req2transform.request_id == models.Request.request_id,
                                                      models.Request.workload_id == workload_id))
        else:
            query = session.query(models.Req2transform.transform_id)

        if request_id:
            query = query.filter(models.Req2transform.request_id == request_id)
        if transform_id:
            query = query.filter(models.Req2transform.transform_id == transform_id)

        tmp = query.all()
        ret_ids = []
        if tmp:
            for t in tmp:
                ret_ids.append(t[0])
        return ret_ids
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('No transforms attached with request id (%s) and transform_id (%s): %s' %
                                  (request_id, transform_id, error))
    except Exception as error:
        raise error


@read_session
def get_transforms(request_id=None, workload_id=None, transform_id=None, to_json=False, session=None):
    """
    Get transforms or raise a NoObject exception.

    :param request_id: Request id.
    :param workload_id: Workload id.
    :param transform_id: Transform id.
    :param session: The database session in use.

    :raises NoObject: If no transform is founded.

    :returns: list of transforms.
    """
    try:
        if workload_id:
            subquery = session.query(models.Req2transform.transform_id)\
                              .join(models.Request, and_(models.Req2transform.request_id == models.Request.request_id,
                                                         models.Request.workload_id == workload_id))
        else:
            subquery = session.query(models.Req2transform.transform_id)

        if request_id:
            subquery = subquery.filter(models.Req2transform.request_id == request_id)
        if transform_id:
            subquery = subquery.filter(models.Req2transform.transform_id == transform_id)
        subquery = subquery.subquery()

        query = session.query(models.Transform)\
                       .join(subquery, and_(subquery.c.transform_id == models.Transform.transform_id))

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
        raise exceptions.NoObject('No transforms attached with request id (%s): %s' %
                                  (request_id, error))
    except Exception as error:
        raise error


@read_session
def get_transforms_by_status(status, period=None, locking=False, bulk_size=None, to_json=False, session=None):
    """
    Get transforms or raise a NoObject exception.

    :param status: Transform status or list of transform status.
    :param period: Time period in seconds.
    :param locking: Whether to retrieved unlocked items.
    :param to_json: return json format.

    :param session: The database session in use.

    :raises NoObject: If no transform is founded.

    :returns: list of transform.
    """
    try:
        if not isinstance(status, (list, tuple)):
            status = [status]
        if len(status) == 1:
            status = [status[0], status[0]]

        query = session.query(models.Transform)\
                       .filter(models.Transform.status.in_(status))\
                       .filter(models.Transform.next_poll_at < datetime.datetime.utcnow())

        if period:
            query = query.filter(models.Transform.updated_at < datetime.datetime.utcnow() - datetime.timedelta(seconds=period))
        if locking:
            query = query.filter(models.Transform.locking == TransformLocking.Idle)

        query = query.order_by(asc(models.Transform.updated_at)).order_by(desc(models.Transform.priority))

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
        raise exceptions.NoObject('No transforms attached with status (%s): %s' %
                                  (status, error))
    except Exception as error:
        raise error


@transactional_session
def update_transform(transform_id, parameters, session=None):
    """
    update a transform.

    :param transform_id: the transform id.
    :param parameters: A dictionary of parameters.
    :param session: The database session in use.

    :raises NoObject: If no content is founded.
    :raises DatabaseException: If there is a database error.

    """
    try:
        parameters['updated_at'] = datetime.datetime.utcnow()
        if 'status' in parameters and parameters['status'] in [TransformStatus.Finished, TransformStatus.Finished.value,
                                                               TransformStatus.Failed, TransformStatus.Failed.value]:
            parameters['finished_at'] = datetime.datetime.utcnow()

        session.query(models.Transform).filter_by(transform_id=transform_id)\
               .update(parameters, synchronize_session=False)
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Transfrom %s cannot be found: %s' % (transform_id, error))


@transactional_session
def delete_transform(transform_id=None, session=None):
    """
    delete a transform.

    :param transform_id: The id of the transform.
    :param session: The database session in use.

    :raises NoObject: If no content is founded.
    :raises DatabaseException: If there is a database error.
    """
    try:
        session.query(models.Req2transform).filter_by(transform_id=transform_id).delete()
        session.query(models.Transform).filter_by(transform_id=transform_id).delete()
    except sqlalchemy.orm.exc.NoResultFound as error:
        raise exceptions.NoObject('Transfrom %s cannot be found: %s' % (transform_id, error))


@transactional_session
def clean_locking(time_period=3600, session=None):
    """
    Clearn locking which is older than time period.

    :param time_period in seconds
    """

    params = {'locking': 0}
    session.query(models.Transform).filter(models.Transform.locking == TransformLocking.Locking)\
           .filter(models.Transform.updated_at < datetime.datetime.utcnow() - datetime.timedelta(seconds=time_period))\
           .update(params, synchronize_session=False)


@transactional_session
def clean_next_poll_at(status, session=None):
    """
    Clearn next_poll_at.

    :param status: status of the transform
    """
    if not isinstance(status, (list, tuple)):
        status = [status]
    if len(status) == 1:
        status = [status[0], status[0]]

    params = {'next_poll_at': datetime.datetime.utcnow()}
    session.query(models.Transform).filter(models.Transform.status.in_(status))\
           .update(params, synchronize_session=False)
