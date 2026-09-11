import cpp
import semmle.code.cpp.dataflow.new.DataFlow

/**
 * Remote / user-controlled sources for C++.
 */
predicate enhancedSource(DataFlow::Node source) {
  httpRequestSource(source) or
  stdinSource(source) or
  envVarSource(source) or
  networkReadSource(source)
}

/** HTTP framework sources — oatpp, pistache, crow, drogon */
predicate httpRequestSource(DataFlow::Node source) {
  exists(FunctionCall call |
    (call.getTarget().getName() = "getPathVariable" or
    call.getTarget().getName() = "getQueryParameter" or
    call.getTarget().getName() = "getBody" or
    call.getTarget().getName() = "readBodyToString" or
    call.getTarget().getName() = "readBodyToDto") and
    source.asExpr() = call
  )
  or
  exists(FunctionCall call |
    (call.getTarget().getName() = "getParameter" or
    call.getTarget().getName() = "getBody" or
    call.getTarget().getName() = "getHeader" or
    call.getTarget().getName() = "getJsonObject" or
    call.getTarget().getName() = "jsonBody") and
    source.asExpr() = call
  )
  or
  // cpp-httplib: req.get_param_value("x") / req.get_header_value("x") / req.body
  exists(FunctionCall call |
    call.getTarget().getName() = ["get_param_value", "get_header_value", "get_file_value"] and
    source.asExpr() = call
  )
  or
  exists(FieldAccess fa |
    fa.getTarget().getName() = "body" and
    fa.getQualifier().getType().getName().matches("%Request%") and
    source.asExpr() = fa
  )
  or
  exists(Parameter p |
    (p.getName().toLowerCase().matches("%req%") or
    p.getName().toLowerCase().matches("%request%") or
    p.getName().toLowerCase().matches("%body%") or
    p.getName().toLowerCase().matches("%param%")) and
    source.asExpr() = p.getAnAccess()
  )
}

/**
 * Standard input reads. These functions write the data into a buffer/string
 * passed by pointer or reference, not into their return value — the return
 * value is typically just a status code (or, for fgets/gets, an alias of the
 * same buffer that dataflow does not know is the same memory) — so the source
 * node must be the out-argument itself for taint to reach anything downstream.
 */
predicate stdinSource(DataFlow::Node source) {
  exists(FunctionCall call | call.getTarget().getName() = "fgets" | source.asExpr() = call.getArgument(0))
  or
  exists(FunctionCall call | call.getTarget().getName() = "gets" | source.asExpr() = call.getArgument(0))
  or
  // scanf(fmt, &a, &b, ...) / fscanf(stream, fmt, &a, ...): every out-arg after the format string
  exists(FunctionCall call, int i |
    call.getTarget().getName() = "scanf" and i >= 1 and source.asExpr() = call.getArgument(i)
    or
    call.getTarget().getName() = "fscanf" and i >= 2 and source.asExpr() = call.getArgument(i)
  )
  or
  exists(FunctionCall call | call.getTarget().getName() = "fread" | source.asExpr() = call.getArgument(0))
  or
  // POSIX getline(char **lineptr, size_t *n, FILE*) vs. C++ std::getline(istream&, string&)
  exists(FunctionCall call |
    call.getTarget().getName() = "getline" and
    source.asExpr() = call.getArgument([0, 1])
  )
}

/** Environment variable reads */
predicate envVarSource(DataFlow::Node source) {
  exists(FunctionCall call |
    call.getTarget().getName() = "getenv" and
    source.asExpr() = call
  )
}

/** Network / fd read operations: the data lands in the buffer argument, not
 *  the returned byte count. */
predicate networkReadSource(DataFlow::Node source) {
  exists(FunctionCall call |
    call.getTarget().getName() = ["recv", "recvfrom", "read", "pread"] and
    source.asExpr() = call.getArgument(1)
  )
  or
  exists(FunctionCall call |
    call.getTarget().getName() = "recvmsg" and source.asExpr() = call.getArgument(1)
  )
}

string getRemoteSourceCategory(DataFlow::Node source) {
  httpRequestSource(source) and result = "HTTP_REQUEST" or
  stdinSource(source) and result = "STDIN" or
  envVarSource(source) and result = "ENV_VAR" or
  networkReadSource(source) and result = "NETWORK_READ"
}
