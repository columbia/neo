import javascript
private import semmle.javascript.dataflow.DataFlow

/**
 * Enhanced privileged operations sink for JavaScript/Node.js.
 */
predicate enhancedSink(DataFlow::Node sink) {
  fileSystemSink(sink)
  or
  processExecutionSink(sink)
  or
  databaseOperationSink(sink)
  or
  dynamicCodeExecutionSink(sink)
  or
  highConfidenceUserDefinedSink(sink)
}

/**
 * File system operations.
 */
private predicate fileSystemSink(DataFlow::Node sink) {
  exists(DataFlow::InvokeNode call |
    call.getCalleeName() in ["writeFile", "writeFileSync", "appendFile", "appendFileSync",
                              "unlink", "unlinkSync", "rmdir", "rmdirSync", "rm", "rmSync",
                              "mkdir", "mkdirSync", "rename", "renameSync", "chmod", "chmodSync",
                              "chown", "chownSync", "copyFile", "copyFileSync"] and
    sink = call.getAnArgument()
  )
}

/**
 * Process execution operations.
 */
private predicate processExecutionSink(DataFlow::Node sink) {
  exists(DataFlow::InvokeNode call |
    call.getCalleeName() in ["exec", "execSync", "execFile", "execFileSync",
                              "spawn", "spawnSync", "fork"] and
    sink = call.getArgument(0)
  )
}

/**
 * Database operations.
 */
private predicate databaseOperationSink(DataFlow::Node sink) {
  exists(DataFlow::InvokeNode call |
    call.getCalleeName() in ["query", "execute", "run", "all", "get", "exec",
                              "find", "findOne", "insertOne", "insertMany",
                              "updateOne", "updateMany", "deleteOne", "deleteMany", "aggregate"] and
    sink = call.getAnArgument()
  )
}

/**
 * Dynamic code execution.
 */
private predicate dynamicCodeExecutionSink(DataFlow::Node sink) {
  exists(DataFlow::InvokeNode call |
    call.getCalleeName() in ["eval", "Function", "runInContext", "runInNewContext", "runInThisContext"] and
    sink = call.getAnArgument()
  )
  or
  // require with dynamic path
  exists(DataFlow::InvokeNode call |
    call.getCalleeName() = "require" and
    not exists(call.getArgument(0).getStringValue()) and
    sink = call.getArgument(0)
  )
}

/**
 * User-defined operations with security implications.
 */
private predicate highConfidenceUserDefinedSink(DataFlow::Node sink) {
  exists(DataFlow::InvokeNode call |
    sink = call.getAnArgument() and
    (
      commandExecutionPattern(call) or
      userManagementPattern(call) or
      permissionRolePattern(call) or
      passwordCredentialPattern(call) or
      systemAdminPattern(call)
    )
  )
}

/**
 * Command execution patterns.
 */
private predicate commandExecutionPattern(DataFlow::InvokeNode call) {
  call.getCalleeName().regexpMatch(".*(?i)(execut|run|invok|launch|start|call).*(command|cmd|process|script|shell|bash).*") or
  call.getCalleeName().regexpMatch(".*(?i)(command|cmd|process|script|shell|bash).*(execut|run|invok|launch|start|call).*")
}

/**
 * User management patterns.
 */
private predicate userManagementPattern(DataFlow::InvokeNode call) {
  call.getCalleeName().regexpMatch(".*(?i)(creat|add|insert|new).*(user|account|member|person).*") or
  call.getCalleeName().regexpMatch(".*(?i)(delet|remov|destroy|kill).*(user|account|member|person).*") or
  call.getCalleeName().regexpMatch(".*(?i)(updat|modif|chang|edit).*(user|account|member|person).*") or
  call.getCalleeName().regexpMatch(".*(?i)(user|account|member|person).*(creat|add|delet|remov|updat|modif).*") or
  call.getCalleeName().regexpMatch(".*(?i)(lock|unlock|enabl|disabl|activ|deactiv).*(user|account).*") or
  call.getCalleeName().regexpMatch(".*(?i)(user|account).*(lock|unlock|enabl|disabl|activ|deactiv).*")
}

/**
 * Permission/role patterns.
 */
private predicate permissionRolePattern(DataFlow::InvokeNode call) {
  call.getCalleeName().regexpMatch(".*(?i)(grant|assign|add|giv).*(permission|privil|right|access|role|author).*") or
  call.getCalleeName().regexpMatch(".*(?i)(revok|remov|delet|deny|block).*(permission|privil|right|access|role|author).*") or
  call.getCalleeName().regexpMatch(".*(?i)(permission|privil|right|access|role|author).*(grant|assign|revok|remov|add|giv|delet).*") or
  call.getCalleeName().regexpMatch(".*(?i)(elevat|promot|demot|upgrad|downgrad).*(user|role|privil|access).*")
}

/**
 * Password/credential patterns.
 */
private predicate passwordCredentialPattern(DataFlow::InvokeNode call) {
  (
    call.getCalleeName().regexpMatch(".*(?i)(set|chang|updat|reset|modif|alter).*(password|passwd|pwd|credential|secret|key|token).*") or
    call.getCalleeName().regexpMatch(".*(?i)(password|passwd|pwd|credential|secret|key|token).*(set|chang|updat|reset|modif|alter).*") or
    call.getCalleeName().regexpMatch(".*(?i)(generat|creat|produc|make|build).*(password|passwd|pwd|credential|secret|key|token).*") or
    call.getCalleeName().regexpMatch(".*(?i)(password|passwd|pwd|credential|secret|key|token).*(generat|creat|produc|make|build).*") or
    call.getCalleeName().regexpMatch(".*(?i)(encrypt|decrypt|hash|unhash|sign|verify).*(password|passwd|pwd|credential|secret).*")
  ) and
  not call.getCalleeName().regexpMatch("^(?i)(is|has|can|check|verif|valid|test|get|read|load|fetch|retrieve).*")
}

/**
 * System/admin patterns.
 */
private predicate systemAdminPattern(DataFlow::InvokeNode call) {
  (
    call.getCalleeName().regexpMatch(".*(?i)(admin|administrat|manag|control|govern|supervis).*(system|server|service|resource).*") or
    call.getCalleeName().regexpMatch(".*(?i)(system|server|service|resource).*(admin|administrat|manag|control|govern|supervis).*") or
    call.getCalleeName().regexpMatch(".*(?i)(shutdown|restart|reboot|reload|refresh|stop|start|kill|terminat).*(system|server|service|process).*") or
    call.getCalleeName().regexpMatch(".*(?i)(backup|restor|recover|migrat|deploy|install|uninstall).*(system|database|service|application).*") or
    call.getCalleeName().regexpMatch(".*(?i)(configur|setting|property).*(chang|updat|modif|set|reset).*")
  ) and
  not call.getCalleeName().regexpMatch("^(?i)(is|has|can|check|verif|valid|test|get|read|load|fetch|retrieve).*")
}
