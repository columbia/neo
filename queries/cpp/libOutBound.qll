import cpp
import semmle.code.cpp.dataflow.new.DataFlow

predicate outBoundSink(DataFlow::Node sink) {
  httpClientOutbound(sink) or
  networkWriteOutbound(sink) or
  executePrivilegedOperation(sink)
}

predicate httpClientOutbound(DataFlow::Node sink) {
  exists(FunctionCall call |
    (call.getTarget().getName().toLowerCase().matches("%curlopt%") or
    call.getTarget().getName().toLowerCase().matches("%curl_easy_setopt%") or
    call.getTarget().getName().toLowerCase().matches("%setbody%") or
    call.getTarget().getName().toLowerCase().matches("%seturl%")) and
    sink.asExpr() = call.getAnArgument()
  )
  or
  // cpr::Get/Post/... and httplib::Client-style `cli.Get(path)` / `cli.Post(path, body, type)`
  exists(FunctionCall call |
    call.getTarget().getName() in ["Get", "Post", "Put", "Delete", "Patch", "Head"] and
    (call.getTarget().getNamespace().getName() = "cpr" or
     call.getQualifier().getType().getName().matches(["%Client%", "%Session%"])) and
    sink.asExpr() = call.getAnArgument()
  )
}

predicate networkWriteOutbound(DataFlow::Node sink) {
  exists(FunctionCall call |
    (call.getTarget().getName() = "send" or
    call.getTarget().getName() = "sendto" or
    call.getTarget().getName() = "sendmsg" or
    call.getTarget().getName() = "write" or
    call.getTarget().getName() = "fwrite") and
    sink.asExpr() = call.getAnArgument()
  )
}

predicate executePrivilegedOperation(DataFlow::Node sink) {
  exists(FunctionCall call |
    (call.getTarget().getName() = "system" or
    call.getTarget().getName() = "popen" or
    call.getTarget().getName() = "execl" or
    call.getTarget().getName() = "execle" or
    call.getTarget().getName() = "execlp" or
    call.getTarget().getName() = "execv" or
    call.getTarget().getName() = "execve" or
    call.getTarget().getName() = "execvp") and
    sink.asExpr() = call.getAnArgument()
  )
}

predicate outboundTaintStep(DataFlow::Node node1, DataFlow::Node node2) {
  exists(AddressOfExpr addr |
    addr.getOperand() = node1.asExpr() and
    node2.asExpr() = addr
  )
}

string getOutboundCategory(DataFlow::Node sink) {
  httpClientOutbound(sink) and result = "HTTP_CLIENT" or
  networkWriteOutbound(sink) and result = "NETWORK_WRITE" or
  executePrivilegedOperation(sink) and result = "PROCESS_EXECUTION"
}
