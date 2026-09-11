import csharp
import semmle.code.csharp.dataflow.DataFlow

/**
 * Enhanced privileged operations sink.
 */
predicate enhancedSink(DataFlow::Node sink) {
  fileSystemSink(sink)
  or
  processExecutionSink(sink)
  or
  databaseOperationSink(sink)
  or
  networkOperationSink(sink)
  or
  reflectionOperationSink(sink)
  or
  systemConfigSink(sink)
  or
  highConfidenceUserDefinedSink(sink)
}

/**
 * File system operations.
 */
private predicate fileSystemSink(DataFlow::Node sink) {
  exists(MethodCall mc |
    mc.getTarget().getDeclaringType().getFullyQualifiedName().matches("System.IO.File") and
    mc.getTarget().getName() in ["Delete", "Move", "Copy", "Create", "WriteAllText",
                                  "WriteAllBytes", "WriteAllLines", "AppendAllText",
                                  "AppendAllLines", "Replace", "Encrypt", "Decrypt"] and
    sink.asExpr() = mc.getAnArgument()
  )
  or
  exists(MethodCall mc |
    mc.getTarget().getDeclaringType().getFullyQualifiedName().matches("System.IO.Directory") and
    mc.getTarget().getName() in ["CreateDirectory", "Delete", "Move"] and
    sink.asExpr() = mc.getAnArgument()
  )
  or
  exists(ObjectCreation oc |
    oc.getType().getFullyQualifiedName().matches("System.IO.FileStream") and
    sink.asExpr() = oc.getAnArgument()
  )
  or
  exists(MethodCall mc |
    mc.getTarget().getDeclaringType().getFullyQualifiedName().matches("System.IO.Path") and
    mc.getTarget().getName() in ["Combine", "GetFullPath"] and
    sink.asExpr() = mc.getAnArgument()
  )
}

/**
 * Process execution operations.
 */
private predicate processExecutionSink(DataFlow::Node sink) {
  exists(MethodCall mc |
    mc.getTarget().getDeclaringType().getFullyQualifiedName()
        .matches("System.Diagnostics.Process") and
    mc.getTarget().getName() = "Start" and
    sink.asExpr() = mc.getAnArgument()
  )
  or
  exists(PropertyWrite pw, AssignExpr assign |
    assign.getLValue() = pw and
    pw.getTarget().getDeclaringType().getFullyQualifiedName()
        .matches("System.Diagnostics.ProcessStartInfo") and
    pw.getTarget().getName() in ["FileName", "Arguments"] and
    sink.asExpr() = assign.getRValue()
  )
  or
  exists(ObjectCreation oc |
    oc.getType().getFullyQualifiedName().matches("System.Diagnostics.ProcessStartInfo") and
    sink.asExpr() = oc.getAnArgument()
  )
}

/**
 * Database operations (ADO.NET, Dapper, EF Core raw SQL).
 */
private predicate databaseOperationSink(DataFlow::Node sink) {
  // ADO.NET: SqlCommand with CommandText
  exists(PropertyWrite pw, AssignExpr assign |
    assign.getLValue() = pw and
    pw.getTarget().getName() = "CommandText" and
    pw.getTarget().getDeclaringType().getName().matches("%Command") and
    sink.asExpr() = assign.getRValue()
  )
  or
  // ADO.NET: constructor with SQL string
  exists(ObjectCreation oc |
    oc.getType().getName().matches("%Command") and
    sink.asExpr() = oc.getArgument(0)
  )
  or
  // EF Core: ExecuteSqlRaw / ExecuteSqlInterpolated
  exists(MethodCall mc |
    mc.getTarget().getName() in ["ExecuteSqlRaw", "ExecuteSqlRawAsync",
                                  "FromSqlRaw", "SqlQuery"] and
    sink.asExpr() = mc.getArgument(0)
  )
  or
  // Dapper: Execute / Query
  exists(MethodCall mc |
    mc.getTarget().getName() in ["Execute", "ExecuteAsync", "Query", "QueryAsync",
                                  "QueryFirst", "QueryFirstAsync", "QuerySingle",
                                  "QuerySingleAsync"] and
    mc.getTarget().getDeclaringType().getFullyQualifiedName().matches("Dapper.%") and
    sink.asExpr() = mc.getAnArgument()
  )
}

/**
 * Network operations.
 */
private predicate networkOperationSink(DataFlow::Node sink) {
  exists(MethodCall mc |
    mc.getTarget().getDeclaringType().getFullyQualifiedName()
        .matches("System.Net.Http.HttpClient") and
    mc.getTarget().getName() in ["GetAsync", "PostAsync", "PutAsync", "DeleteAsync",
                                  "PatchAsync", "SendAsync", "GetStringAsync"] and
    sink.asExpr() = mc.getArgument(0)
  )
  or
  exists(ObjectCreation oc |
    oc.getType().getFullyQualifiedName().matches("System.Net.Http.HttpRequestMessage") and
    sink.asExpr() = oc.getAnArgument()
  )
}

/**
 * Reflection and code execution.
 */
private predicate reflectionOperationSink(DataFlow::Node sink) {
  exists(MethodCall mc |
    mc.getTarget().getDeclaringType().getFullyQualifiedName().matches("System.Reflection.%") and
    mc.getTarget().getName() in ["InvokeMember", "CreateInstance", "GetType"] and
    sink.asExpr() = mc.getAnArgument()
  )
  or
  // Type.GetType() with user-supplied string
  exists(MethodCall mc |
    mc.getTarget().getDeclaringType().getFullyQualifiedName().matches("System.Type") and
    mc.getTarget().getName() = "GetType" and
    sink.asExpr() = mc.getArgument(0)
  )
  or
  // Assembly.Load with user-supplied path/name
  exists(MethodCall mc |
    mc.getTarget().getDeclaringType().getFullyQualifiedName().matches("System.Reflection.Assembly") and
    mc.getTarget().getName() in ["Load", "LoadFrom", "LoadFile", "LoadWithPartialName"] and
    sink.asExpr() = mc.getArgument(0)
  )
}

/**
 * System configuration changes.
 */
private predicate systemConfigSink(DataFlow::Node sink) {
  exists(PropertyWrite pw, AssignExpr assign |
    assign.getLValue() = pw and
    pw.getTarget().getDeclaringType().getFullyQualifiedName().matches("System.Environment") and
    pw.getTarget().getName() = "CurrentDirectory" and
    sink.asExpr() = assign.getRValue()
  )
  or
  exists(MethodCall mc |
    mc.getTarget().getDeclaringType().getFullyQualifiedName().matches("System.Environment") and
    mc.getTarget().getName() = "SetEnvironmentVariable" and
    sink.asExpr() = mc.getAnArgument()
  )
}

/**
 * High-confidence user-defined privileged operations based on naming patterns.
 */
private predicate highConfidenceUserDefinedSink(DataFlow::Node sink) {
  exists(MethodCall mc |
    sink.asExpr() = mc.getAnArgument() and
    not mc.getTarget().getDeclaringType().getFullyQualifiedName()
        .matches(["System.%", "Microsoft.%"]) and
    (
      commandExecutionPattern(mc) or
      userManagementPattern(mc) or
      permissionRolePattern(mc) or
      passwordCredentialPattern(mc) or
      systemAdminPattern(mc)
    )
  )
}

private predicate commandExecutionPattern(MethodCall mc) {
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:execut|run|invok|launch|start|call).*(?:command|cmd|process|script|shell).*")
  or
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:command|cmd|process|script|shell).*(?:execut|run|invok|launch|start|call).*")
}

private predicate userManagementPattern(MethodCall mc) {
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:creat|add|insert|new).*(?:user|account|member|person).*")
  or
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:delet|remov|destroy).*(?:user|account|member|person).*")
  or
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:updat|modif|chang|edit).*(?:user|account|member|person).*")
  or
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:lock|unlock|enabl|disabl|activ|deactiv).*(?:user|account).*")
}

private predicate permissionRolePattern(MethodCall mc) {
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:grant|assign|add|giv).*(?:permission|privil|right|access|role|author).*")
  or
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:revok|remov|delet|deny|block).*(?:permission|privil|right|access|role|author).*")
  or
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:elevat|promot|demot|upgrad|downgrad).*(?:user|role|privil|access).*")
}

private predicate passwordCredentialPattern(MethodCall mc) {
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:set|chang|updat|reset|modif|alter).*(?:password|passwd|pwd|credential|secret|key|token).*")
  or
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:generat|creat|produc|make|build).*(?:password|passwd|pwd|credential|secret|key|token).*")
}

private predicate systemAdminPattern(MethodCall mc) {
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:shutdown|restart|reboot|reload|stop|start|kill|terminat).*(?:system|server|service|process).*")
  or
  mc.getTarget().getName().toLowerCase()
      .regexpMatch(".*(?:backup|restor|recover|migrat|deploy|install|uninstall).*(?:system|database|service|application).*")
}

/**
 * Gets the privileged operation category.
 */
string getPrivilegedSinkCategory(DataFlow::Node sink) {
  fileSystemSink(sink) and result = "FILE_SYSTEM"
  or
  processExecutionSink(sink) and result = "PROCESS_EXECUTION"
  or
  databaseOperationSink(sink) and result = "DATABASE_OPERATION"
  or
  networkOperationSink(sink) and result = "NETWORK_OPERATION"
  or
  reflectionOperationSink(sink) and result = "REFLECTION_OPERATION"
  or
  systemConfigSink(sink) and result = "SYSTEM_CONFIG"
  or
  highConfidenceUserDefinedSink(sink) and result = "USER_DEFINED"
}
