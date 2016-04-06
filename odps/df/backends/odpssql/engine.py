#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import time
import sys

from ....errors import ODPSError

from ....utils import init_progress_bar, TEMP_TABLE_PREFIX
from ....models import Partition
from ....tempobj import register_temp_table
from ....types import PartitionSpec
from ...core import DataFrame
from ...expr.reduction import *
from ...expr.arithmetic import And, Equal
from ..core import Engine
from ..frame import ResultFrame
from . import types
from . import analyzer as ana
from ..errors import CompileError
from .context import ODPSContext, UDF_CLASS_NAME
from .compiler import OdpsSQLCompiler
from .codegen import gen_udf


class ODPSEngine(Engine):
    def __init__(self, odps, global_optimize=True):
        self._odps = odps
        self._ctx = ODPSContext(self._odps)

        self._global_optimize = global_optimize

    def _get_task_percent(self, instance, task_name):
        progress = instance.get_task_progress(task_name)

        if len(progress.stages) > 0:
            all_percent = sum((float(stage.terminated_workers) / stage.total_workers)
                              for stage in progress.stages if stage.total_workers > 0)
            return all_percent / len(progress.stages)
        else:
            return 0

    @classmethod
    def _to_stdout(cls, msg):
        print(msg)

    def _log(self, msg):
        if options.verbose:
            (options.verbose_log or self._to_stdout)(msg)

    @classmethod
    def _is_source_table(cls, expr):
        return isinstance(expr, CollectionExpr) and \
               expr._source_data is not None

    def _run(self, sql, bar, start_progress=0, max_progress=1, async=False, hints=None):
        self._ctx.create_udfs()
        instance = self._odps.run_sql(sql, hints=hints)

        self._log('logview:')
        self._log(self._odps.get_logview_address(instance.id, 24))

        if async:
            return instance

        try:
            percent = 0
            while not instance.is_terminated():
                task_names = instance.get_task_names()
                last_percent = percent
                if len(task_names) > 0:
                    percent = sum(self._get_task_percent(instance, name)
                                  for name in task_names) / len(task_names)
                else:
                    percent = 0
                percent = min(1, max(percent, last_percent))
                bar.update(start_progress + percent * max_progress)

                time.sleep(1)

            instance.wait_for_success()
            bar.update(start_progress + max_progress)
        except KeyboardInterrupt:
            instance.stop()
            self._ctx.close()
            sys.exit(1)

        return instance

    @classmethod
    def _is_source_column(cls, expr, table):
        if not isinstance(expr, Column):
            return False

        odps_schema = table.schema
        if odps_schema.is_partition(expr.source_name):
            return False

        return True

    @classmethod
    def _is_source_partition(cls, expr, table):
        if not isinstance(expr, Column):
            return False

        odps_schema = table.schema
        if not odps_schema.is_partition(expr.source_name):
            return False

        return True

    @classmethod
    def _can_propagate(cls, collection, no_filter=False, no_projection=False):
        if not isinstance(collection, CollectionExpr):
            return False

        if cls._is_source_table(collection):
            return True
        if not no_filter and cls._filter_on_partition(collection):
            return True
        if not no_projection and cls._projection_on_source(collection):
            return True
        return False

    @classmethod
    def _projection_on_source(cls, expr):
        cols = []

        if isinstance(expr, ProjectCollectionExpr) and \
                cls._can_propagate(expr.input, no_projection=True):
            for col in expr.fields:
                source = next(expr.data_source())
                if not cls._is_source_column(col, source):
                    return False
                cols.append(col.source_name)
            return cols
        return False

    @classmethod
    def _filter_on_partition(cls, expr):
        if not isinstance(expr, FilterCollectionExpr) or \
                not cls._can_propagate(expr.input, no_filter=True):
            return False

        cols = []
        values = []

        def extract(expr):
            if isinstance(expr, Column):
                if cls._is_source_partition(expr, next(expr.data_source())):
                    cols.append(expr.source_name)
                    return True
                else:
                    return False

            if isinstance(expr, And):
                for child in expr.args:
                    if not extract(child):
                        return False
            elif isinstance(expr, Equal) and isinstance(expr._rhs, Scalar):
                if extract(expr._lhs):
                    values.append(expr._rhs.value)
                    return True
            else:
                return False

        if not extract(expr.predicate):
            return False

        if len(cols) == len(values):
            return list(zip(cols, values))
        return False

    def _handle_cases(self, expr, bar=None, start_progress=0, max_progress=1,
                      head=None, tail=None):
        if bar is None:
            bar = init_progress_bar()

        if isinstance(expr, (ProjectCollectionExpr, Summary)) and \
                len(expr.fields) == 1 and \
                isinstance(expr.fields[0], Count) and \
                self._is_source_table(expr.input):
            expr = expr.fields[0]

        columns, partition, count = (None, ) * 3
        if isinstance(expr, Count):
            if isinstance(expr.input, Column):
                input = expr.input.input
            else:
                input = expr.input
        elif isinstance(expr, SliceCollectionExpr):
            input = expr.input
        else:
            input = expr

        if not self._can_propagate(input):
            return

        while True:
            ret = self._filter_on_partition(input)
            if ret:
                partition = ','.join(['='.join(it) for it in ret])
                input = input.input
                continue

            ret = self._projection_on_source(input)
            if ret:
                columns = ret
                input = input.input
                continue
            break

        table = next(expr.data_source())
        partition_size = len(partition.split(',')) if partition is not None else 0
        if table.schema._partitions is not None and \
                len(table.schema._partitions) != partition_size:
            return

        if isinstance(expr, Count):
            try:
                with table.open_reader(reopen=True, partition=partition) as reader:
                    bar.update(start_progress + max_progress)
                    return reader.count
            except ODPSError:
                return
        else:
            self._log('Try to fetch data from tunnel')
            if isinstance(expr, SliceCollectionExpr):
                count = expr.stop
            try:
                with table.open_reader(reopen=True, partition=partition) as reader:
                    if tail is not None:
                        start = max(reader.count - tail, 0)
                    else:
                        start = None
                    if head is not None:
                        count = min(count, head) if count is not None else head

                    data = []
                    curr = itertools.count(0)
                    size = count or reader.count
                    for r in reader.read(start=start, count=count, columns=columns):
                        i = next(curr)
                        if i % 50 == 0:
                            bar.update(start_progress + min(float(i) / size * max_progress, 1))
                        data.append(r.values)
                    bar.update(start_progress + max_progress)

                    schema = types.df_schema_to_odps_schema(expr._schema, ignorecase=True)
                    return ResultFrame(data, schema=schema)
            except ODPSError:
                return

    def execute(self, expr, bar=None, async=False, start_progress=0,
                max_progress=1, lifecycle=None, head=None, tail=None, hints=None, **kw):
        close_bar = bar is None
        bar = bar or init_progress_bar()
        lifecycle = lifecycle or options.temp_lifecycle

        if isinstance(expr, Scalar) and expr.value is not None:
            bar.update(start_progress+max_progress)
            return expr.value

        src_expr = expr
        expr = self._pre_process(expr)

        try:
            result = self._handle_cases(expr, bar, head=head, tail=tail)
        except KeyboardInterrupt:
            sys.exit(1)
        if result is not None:
            try:
                return result
            finally:
                if close_bar:
                    bar.close()

        sql = self._compile(expr)

        cache_data = None
        if isinstance(expr, CollectionExpr):
            tmp_table_name = '%s%s' % (TEMP_TABLE_PREFIX, str(uuid.uuid4()).replace('-', '_'))
            register_temp_table(self._odps, tmp_table_name)
            cache_data = self._odps.get_table(tmp_table_name)

            lifecycle_str = 'LIFECYCLE {0} '.format(lifecycle) if lifecycle is not None else ''
            sql = 'CREATE TABLE {0} {1}AS \n{2}'.format(tmp_table_name, lifecycle_str, sql)

        self._log('Sql compiled:')
        self._log(sql)

        instance = self._run(sql, bar, start_progress=start_progress,
                             max_progress=0.9*max_progress, async=async, hints=hints)

        use_tunnel = kw.get('use_tunnel', True)
        if async:
            engine = self

            global_head, global_tail = head, tail

            class AsyncResult(object):
                @property
                def instance(self):
                    return instance

                def wait(self):
                    instance.wait_for_completion()

                def is_done(self):
                    return instance.is_terminated()

                def fetch(self, head=None, tail=None):
                    head = head or global_head
                    tail = tail or global_tail
                    return engine._fetch(expr, src_expr, instance, bar,
                                         finish_progress=start_progress+max_progress,
                                         close_bar=close_bar, cache_data=cache_data,
                                         head=head, tail=tail, use_tunnel=use_tunnel)

            return AsyncResult()
        else:
            self._ctx.close()  # clear udfs and resources generated
            return self._fetch(expr, src_expr, instance, bar, close_bar=close_bar,
                               cache_data=cache_data, head=head, tail=tail,
                               use_tunnel=use_tunnel)

    def _fetch(self, expr, src_expr, instance, bar, finish_progress=1,
               close_bar=True, cache_data=None, head=None, tail=None, use_tunnel=True):
        if isinstance(expr, (CollectionExpr, Summary)):
            df_schema = expr._schema
            schema = types.df_schema_to_odps_schema(expr._schema, ignorecase=True)
        elif isinstance(expr, SequenceExpr):
            df_schema = Schema.from_lists([expr.name], [expr._data_type])
            schema = types.df_schema_to_odps_schema(df_schema, ignorecase=True)
        else:
            df_schema = None
            schema = None
        try:
            if cache_data is not None:
                if use_tunnel:
                    try:
                        with cache_data.open_reader(reopen=True) as reader:
                            if head:
                                reader = reader[:head]
                            elif tail:
                                start = max(reader.count - tail, 0)
                                reader = reader[start: ]
                            try:
                                return ResultFrame([r.values for r in reader], schema=df_schema)
                            finally:
                                src_expr._cache_data = cache_data
                                bar.update(finish_progress)
                    except ODPSError:
                        # some project has closed the tunnel download
                        # we just ignore the error
                        pass

                if tail:
                    raise NotImplementedError

                try:
                    return ResultFrame(cache_data.head(head or 10000), schema=df_schema)
                finally:
                    src_expr._cache_data = cache_data
                    bar.update(finish_progress)

            with instance.open_reader(schema=schema) as reader:
                if not isinstance(src_expr, Scalar):
                    if head:
                        reader = reader[:head]
                    elif tail:
                        start = max(reader.count - tail, 0)
                        reader = reader[start: ]
                    try:
                        return ResultFrame([r.values for r in reader], schema=df_schema)
                    finally:
                        src_expr._cache_data = cache_data
                        bar.update(finish_progress)
                else:
                    bar.update(finish_progress)
                    odps_type = types.df_type_to_odps_type(src_expr._value_type)
                    res = types.odps_types.validate_value(reader[0][0], odps_type)
                    src_expr._cache_data = res
                    return res
        finally:
            if close_bar:
                bar.close()

    def _optimize(self, expr):
        if self._global_optimize:
            from ..optimize import Optimizer
            expr = Optimizer(expr).optimize()

        expr = ana.Analyzer(expr).analyze()
        return expr

    def _pre_process(self, expr):
        src_expr = expr

        if isinstance(expr, Scalar) and expr.value is not None:
            return expr.value
        elif isinstance(expr, (Scalar, SequenceExpr)):
            expr = self._convert_table(expr)

        replaced = self._ctx.get_replaced_expr(src_expr)
        if replaced is None:
            expr = self._optimize(expr)
            self._ctx.add_replaced_expr(src_expr, expr)
        else:
            expr = replaced

        return expr

    def compile(self, expr, prettify=True):
        expr = self._pre_process(expr)

        return self._compile(expr, prettify=prettify)

    def _compile(self, expr, prettify=False):
        backend = OdpsSQLCompiler(self._ctx, beautify=prettify)

        self._ctx.register_udfs(gen_udf(expr, UDF_CLASS_NAME))

        return backend.compile(expr)

    def persist(self, expr, name, partitions=None, partition=None, project=None, bar=None,
                start_progress=0, max_progress=1, lifecycle=None, hints=None,
                create_table=True, drop_partition=False, create_partition=False, **kw):
        close_bar = bar is None
        bar = bar or init_progress_bar()

        should_cache = False

        table_name = name if project is None else '%s.`%s`' % (project, name)
        if partitions is None and partition is None:
            sql = self.compile(expr, prettify=False)
            lifecycle_str = 'LIFECYCLE {0} '.format(lifecycle) if lifecycle is not None else ''
            sql = 'CREATE TABLE {0} {1}AS \n{2}'.format(table_name, lifecycle_str, sql)

            should_cache = True
        elif partition is not None:
            sql = self.compile(expr, prettify=False)
            t = self._odps.get_table(name, project=project)

            for col in expr.schema.columns:
                if col.name.lower() not in t.schema:
                    raise CompileError('Column %s does not exist in table' % col.name)
                t_col = t.schema[col.name.lower()]
                if types.df_type_to_odps_type(col.type) != t_col.type:
                    raise CompileError('Column %s\'s type does not match, expect %s, got %s' % (
                        col.name, t_col.type, col.type))

            if drop_partition:
                t.delete_partition(partition, if_exists=True)
            if create_partition:
                t.create_partition(partition, if_not_exists=True)

            partition = PartitionSpec(partition)
            sql = 'INSERT OVERWRITE TABLE {0} PARTITION({1}) \n{2}'.format(
                name, partition, sql
            )
        else:
            if isinstance(partitions, tuple):
                partitions = list(partitions)
            if not isinstance(partitions, list):
                partitions = [partitions, ]

            if isinstance(expr, CollectionExpr):
                schema = types.df_schema_to_odps_schema(expr.schema, ignorecase=True)
            else:
                col_name = expr.name
                tp = types.df_type_to_odps_type(expr.dtype)
                schema = Schema.from_lists([col_name, ], [tp, ])

            for p in partitions:
                if p not in schema:
                    raise ValueError(
                            'Partition field(%s) does not exist in DataFrame schema' % p)

            columns = [c for c in schema.columns if c.name not in partitions]
            ps = [Partition(name=t, type=schema.get_type(t)) for t in partitions]
            if create_table:
                self._odps.create_table(name, Schema(columns=columns, partitions=ps), project=project)
            expr = expr[[c.name for c in expr.schema if c.name not in partitions] + partitions]

            sql = self.compile(expr, prettify=False)

            sql = 'INSERT OVERWRITE TABLE {0} PARTITION({1}) \n{2}'.format(
                name, ', '.join(partitions), sql
            )

        self._log('Sql compiled:')
        self._log(sql)

        try:
            self._run(sql, bar, start_progress=start_progress, max_progress=max_progress, hints=hints)
            t = self._odps.get_table(name, project=project)
            if should_cache:
                expr._cache_data = t
            if partition:
                filters = []
                for k in partition.keys:
                    filters.append(lambda x: x[k] == partition[k])
                return DataFrame(t).filter(*filters)
            return DataFrame(t)
        finally:
            if close_bar:
                bar.close()

