import cpp
import semmle.code.cpp.dataflow.new.DataFlow

/**
 * Enhanced privileged operations sink for C++.
 */
predicate enhancedSink(DataFlow::Node sink) {
  fileSystemSink(sink) or
  processExecutionSink(sink) or
  databaseOperationSink(sink) or
  networkOperationSink(sink) or
  permissionChangeSink(sink)
}

/** File system sinks: fopen, open, unlink, rename, chmod, chown, mkdir */
predicate fileSystemSink(DataFlow::Node sink) {
  exists(FunctionCall call |
    (call.getTarget().getName() = "fopen" or
    call.getTarget().getName() = "open" or
    call.getTarget().getName() = "creat" or
    call.getTarget().getName() = "unlink" or
    call.getTarget().getName() = "remove" or
    call.getTarget().getName() = "rename" or
    call.getTarget().getName() = "mkdir" or
    call.getTarget().getName() = "rmdir" or
    call.getTarget().getName() = "chmod" or
    call.getTarget().getName() = "chown" or
    call.getTarget().getName() = "lchown" or
    call.getTarget().getName() = "fchown" or
    call.getTarget().getName() = "symlink" or
    call.getTarget().getName() = "link" or
    call.getTarget().getName() = "mknod") and
    sink.asExpr() = call.getAnArgument()
  )
}

/** Process execution sinks: system, exec* family, popen */
predicate processExecutionSink(DataFlow::Node sink) {
  exists(FunctionCall call |
    (call.getTarget().getName() = "system" or
    call.getTarget().getName() = "popen" or
    call.getTarget().getName() = "execl" or
    call.getTarget().getName() = "execle" or
    call.getTarget().getName() = "execlp" or
    call.getTarget().getName() = "execv" or
    call.getTarget().getName() = "execve" or
    call.getTarget().getName() = "execvp" or
    call.getTarget().getName() = "execvpe" or
    call.getTarget().getName() = "posix_spawn") and
    sink.asExpr() = call.getAnArgument()
  )
}

/** SQL / database query sinks */
predicate databaseOperationSink(DataFlow::Node sink) {
  exists(FunctionCall call |
    (call.getTarget().getName() = "sqlite3_exec" or
    call.getTarget().getName() = "sqlite3_prepare" or
    call.getTarget().getName() = "sqlite3_prepare_v2" or
    call.getTarget().getName() = "sqlite3_prepare_v3") and
    sink.asExpr() = call.getAnArgument()
  )
  or
  exists(FunctionCall call |
    (call.getTarget().getName().toLowerCase().matches("%exec%query%") or
    call.getTarget().getName().toLowerCase().matches("%execute%")) and
    sink.asExpr() = call.getAnArgument()
  )
}

/** Network operation sinks */
predicate networkOperationSink(DataFlow::Node sink) {
  exists(FunctionCall call |
    (call.getTarget().getName() = "connect" or
    call.getTarget().getName() = "bind" or
    call.getTarget().getName() = "listen" or
    call.getTarget().getName() = "sendto" or
    call.getTarget().getName() = "sendmsg" or
    call.getTarget().getName() = "send") and
    sink.asExpr() = call.getAnArgument()
  )
}

/** Permission and credential change sinks */
predicate permissionChangeSink(DataFlow::Node sink) {
  exists(FunctionCall call |
    (call.getTarget().getName() = "setuid" or
    call.getTarget().getName() = "setgid" or
    call.getTarget().getName() = "setreuid" or
    call.getTarget().getName() = "setregid" or
    call.getTarget().getName() = "setresuid" or
    call.getTarget().getName() = "setresgid" or
    call.getTarget().getName() = "seteuid" or
    call.getTarget().getName() = "setegid" or
    call.getTarget().getName() = "capset" or
    call.getTarget().getName() = "prctl") and
    sink.asExpr() = call.getAnArgument()
  )
}

string getPrivilegedSinkCategory(DataFlow::Node sink) {
  fileSystemSink(sink) and result = "FILE_SYSTEM" or
  processExecutionSink(sink) and result = "PROCESS_EXECUTION" or
  databaseOperationSink(sink) and result = "DATABASE_OPERATION" or
  networkOperationSink(sink) and result = "NETWORK_OPERATION" or
  permissionChangeSink(sink) and result = "PERMISSION_CHANGE"
}
