from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import es

from sqlalchemy import types
from sqlalchemy.engine import default
from sqlalchemy.sql import compiler

from . import exceptions

logger = logging.getLogger(__name__)


class ESCompiler(compiler.SQLCompiler):
    pass


class ESTypeCompiler(compiler.GenericTypeCompiler):
    def visit_REAL(self, type_, **kwargs):
        return "DOUBLE"

    def visit_NUMERIC(self, type_, **kwargs):
        return "LONG"

    visit_DECIMAL = visit_NUMERIC
    visit_INTEGER = visit_NUMERIC
    visit_SMALLINT = visit_NUMERIC
    visit_BIGINT = visit_NUMERIC
    visit_BOOLEAN = visit_NUMERIC
    visit_TIMESTAMP = visit_NUMERIC
    visit_DATE = visit_NUMERIC

    def visit_CHAR(self, type_, **kwargs):
        return "STRING"

    visit_NCHAR = visit_CHAR
    visit_VARCHAR = visit_CHAR
    visit_NVARCHAR = visit_CHAR
    visit_TEXT = visit_CHAR

    def visit_DATETIME(self, type_, **kwargs):
        return "DATETIME"

    def visit_TIME(self, type_, **kwargs):
        raise exceptions.NotSupportedError("Type TIME is not supported")

    def visit_BINARY(self, type_, **kwargs):
        raise exceptions.NotSupportedError("Type BINARY is not supported")

    def visit_VARBINARY(self, type_, **kwargs):
        raise exceptions.NotSupportedError("Type VARBINARY is not supported")

    def visit_BLOB(self, type_, **kwargs):
        raise exceptions.NotSupportedError("Type BLOB is not supported")

    def visit_CLOB(self, type_, **kwargs):
        raise exceptions.NotSupportedError("Type CBLOB is not supported")

    def visit_NCLOB(self, type_, **kwargs):
        raise exceptions.NotSupportedError("Type NCBLOB is not supported")


class ESDialect(default.DefaultDialect):

    name = "es"
    scheme = "http"
    driver = "rest"
    preparer = compiler.IdentifierPreparer
    statement_compiler = ESCompiler
    type_compiler = ESTypeCompiler
    supports_alter = False
    supports_pk_autoincrement = False
    supports_default_values = False
    supports_empty_insert = False
    supports_unicode_statements = True
    supports_unicode_binds = True
    returns_unicode_strings = True
    description_encoding = None
    supports_native_boolean = True
    supports_simple_order_by_label = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._server = None
        self.update_from_kwargs(kwargs)

    def update_from_kwargs(self, givenkw):
        kwargs = givenkw.copy() if givenkw else {}
        if "server" in kwargs:
            self._server = kwargs.pop("server")
        return kwargs

    @classmethod
    def dbapi(cls):
        return es

    def create_connect_args(self, url):
        kwargs = {
            "host": url.host,
            "port": url.port or 9000,
            "path": url.database,
            "scheme": self.scheme,
            "user": url.username or None,
            "password": url.password or None,
        }
        if url.query:
            kwargs.update(url.query)

        kwargs = self.update_from_kwargs(kwargs)
        return ([], kwargs)

    def get_schema_names(self, connection, **kwargs):
        return ["default"]

    def has_table(self, connection, table_name, schema=None):
        return table_name in self.get_table_names(connection, schema)

    def get_table_names(self, connection, schema=None, **kwargs):
        query = "SHOW TABLES"
        result = connection.execute(query)
        return [row.name for row in result if row.type != "VIEW" and row.name[0] != "."]

    def get_view_names(self, connection, schema=None, **kwargs):
        return []

    def get_table_options(self, connection, table_name, schema=None, **kwargs):
        return {}

    def get_columns(self, connection, table_name, schema=None, **kwargs):
        query = f"SHOW COLUMNS FROM {table_name}"
        result = connection.execute(query)
        return [
            {
                "name": row.column,
                "type": get_type(row.mapping),
                "nullable": True,
                "default": None,
            }
            for row in result
        ]

    def get_pk_constraint(self, connection, table_name, schema=None, **kwargs):
        return {"constrained_columns": [], "name": None}

    def get_foreign_keys(self, connection, table_name, schema=None, **kwargs):
        return []

    def get_check_constraints(self, connection, table_name, schema=None, **kwargs):
        return []

    def get_table_comment(self, connection, table_name, schema=None, **kwargs):
        return {"text": ""}

    def get_indexes(self, connection, table_name, schema=None, **kwargs):
        return []

    def get_unique_constraints(self, connection, table_name, schema=None, **kwargs):
        return []

    def get_view_definition(self, connection, view_name, schema=None, **kwargs):
        pass

    def do_rollback(self, dbapi_connection):
        pass

    def _check_unicode_returns(self, connection, additional_tests=None):
        return True

    def _check_unicode_description(self, connection):
        return True


ESHTTPDialect = ESDialect


class ESHTTPSDialect(ESDialect):

    scheme = "http"
    default_paramstyle = "pyformat"


def get_type(data_type):
    type_map = {
        "text": types.String,
        "keyword": types.String,
        "integer": types.Integer,
        "half_float": types.Float,
        "geo_point": types.String,
        # TODO get a solution for nested type
        "nested": types.String,
        "datetime": types.DateTime,
        # TODO get a solution for object
        "object": types.BLOB,
        "date": types.Date,
        "long": types.BigInteger,
        "float": types.Float,
        "double": types.Numeric,
        "bytes": types.LargeBinary,
        "boolean": types.Boolean,
        "ip": types.String,
    }
    type_ = type_map.get(data_type)
    if not type_:
        logger.warning(f"Unknown type found {data_type} reverting to string")
        type_ = types.String
    return type_
