# -*- coding: utf-8 -*-

import threading
import jpype
import jpype.dbapi2
from dj_db_conn_pool.core.mixins import PersistentDatabaseWrapperMixin

import logging
logger = logging.getLogger(__name__)

jdbc_type_converters = {}

lock_check_jvm_status = threading.Lock()


class JDBCDatabaseWrapperMixin(PersistentDatabaseWrapperMixin):
    _sql_param_style = 'qmark'

    _sql_converter = staticmethod(lambda sql: sql.replace('%s', '?'))

    @property
    def jdbc_driver(self):
        raise NotImplementedError()

    @property
    def jdbc_url_prefix(self):
        raise NotImplementedError()

    @property
    def jdbc_url(self):
        return '{prefix}//{HOST}:{PORT}/{NAME}'.format(
            prefix=self.jdbc_url_prefix,
            **self.settings_dict
        )

    def get_connection_params(self):
        return self.settings_dict.get('OPTIONS', {})

    def _get_new_connection(self, conn_params):
        with lock_check_jvm_status:
            if not jpype.isJVMStarted():
                jpype.startJVM(ignoreUnrecognized=True)

        conn = jpype.dbapi2.connect(
            self.jdbc_url,
            driver=self.jdbc_driver,
            driver_args=dict(
                user=self.settings_dict['USER'],
                password=self.settings_dict['PASSWORD'],
                **conn_params
            ),
            converters=jdbc_type_converters,
        )

        return conn

    def _close(self):
        if self.connection is not None and self.connection.driver_connection.autocommit:
            # if jdbc connection's autoCommit is on
            # jpype will throw NotSupportedError after rollback called
            # we make a little dynamic patch here, make sure
            # SQLAlchemy will not do rollback before recycling connection
            self.connection._pool._reset_on_return = None

            logger.debug(
                "autoCommit of current JDBC connection to %s %s is on, won't do rollback before returning",
                self.alias, self.connection.driver_connection)

        return super(JDBCDatabaseWrapperMixin, self)._close()
