This takes Java as an example but other languages should all follow it

## Basic query libraries
- libSource.qll -> this defines a `enhancedSource` predicate that enhances the builtin codeql query library to find data sources
- libOutBound.qll -> this defines a `outBoundSink` predicate that finds the outbound function calls
- libSink.qll -> this define a `enhancedSink` predicate that finds basic privilege escalation operations


## DuckDB construction:
- callsites.ql -> this is used to construct the callsites

## Sink identification:
- template_sink_op.qll -> the template produces a library query to locate more customized sinks
- template_sink_checked_op.qll -> the tempalte produces a library query to locate more sinks given the validated checks

- sink_base_check.ql -> the query finds the basic auth checks

## Flow Identification
- template_flow_source_sink.ql -> this *template* is used to produce a query that actually finds the flows for later validation
    * sources: libSources
    * sinks: libSink, additional sinks from customized op and checked op.

- flow_source_outbound.ql -> this query finds the data flow from sources that is sent out
    * sources: libSources
    * sinks: outBound


## Testing queries
At current folder, execute via `run_codeql.sh`
- example/test_libsource.ql
- example/test_libsink.ql
- example/example_flow_source_sink.ql -> find the basic source to sink flows


In the python scripts, the query should be run under current directory. 
The derived queries from templates are put under tmp/
