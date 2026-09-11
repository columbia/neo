import java
import semmle.code.java.dataflow.DataFlow
import semmle.code.java.dataflow.TaintTracking
import semmle.code.java.dataflow.FlowSources

/**
 * Enhanced privileged operations sink - consistent argument identification.
 */
predicate enhancedSink(DataFlow::Node sink) {
  fileSystemSink(sink)
  or
  processExecutionSink(sink)
  or
  networkOperationSink(sink)
  or
  systemConfigSink(sink)
  or
  databaseOperationSink(sink)
  or
  securityOperationSink(sink)
  or
  reflectionOperationSink(sink)
//   or
//   cryptographicOperationSink(sink)
  or
  highConfidenceUserDefinedSink(sink)
  or
  strongAnnotationBasedSink(sink)
}

/**
 * File system operations - consistent argument identification.
 */
private predicate fileSystemSink(DataFlow::Node sink) {
  // File constructors - path argument
  exists(ConstructorCall cc |
    cc.getConstructedType().hasQualifiedName("java.io", "File") and
    cc.getArgument(0) = sink.asExpr()
  ) or
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.nio.file", "Paths") and
    mc.getMethod().getName() = "get" and
    mc.getArgument(0) = sink.asExpr()
  ) or
  // File operations - qualifier (the file object itself)
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.io", "File") and
    mc.getMethod().getName() in ["delete", "mkdir", "mkdirs", "createNewFile", "setWritable", 
                                   "setReadable", "setExecutable", "renameTo"] and
    mc.getQualifier() = sink.asExpr()
  ) or
  // NIO file operations - path arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.nio.file", "Files") and
    mc.getMethod().getName() in ["delete", "deleteIfExists", "move", "copy", "createDirectory", 
                                  "createDirectories", "write", "setPosixFilePermissions"] and
    mc.getAnArgument() = sink.asExpr()
  )
}

/**
 * Process execution operations - consistent argument identification.
 */
private predicate processExecutionSink(DataFlow::Node sink) {
  // Runtime.exec - command argument
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.lang", "Runtime") and
    mc.getMethod().getName() = "exec" and
    mc.getAnArgument() = sink.asExpr()
  ) or
  // ProcessBuilder.command - command arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.lang", "ProcessBuilder") and
    mc.getMethod().getName() in ["command", "directory"] and
    mc.getAnArgument() = sink.asExpr()
  ) or
  // ProcessBuilder constructor - command arguments
  exists(ConstructorCall cc |
    cc.getConstructedType().hasQualifiedName("java.lang", "ProcessBuilder") and
    cc.getAnArgument() = sink.asExpr()
  )
}

/**
 * Network operations - consistent argument identification.
 */
private predicate networkOperationSink(DataFlow::Node sink) {
  // Socket constructors - host/port arguments
  exists(ConstructorCall cc |
    cc.getConstructedType().hasQualifiedName("java.net", ["Socket", "ServerSocket", "DatagramSocket"]) and
    cc.getAnArgument() = sink.asExpr()
  ) or
  // URL operations - the URL qualifier
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.net", "URL") and
    mc.getMethod().getName() = "openConnection" and
    mc.getQualifier() = sink.asExpr()
  )
}

/**
 * System configuration - consistent argument identification.
 */
private predicate systemConfigSink(DataFlow::Node sink) {
  // System property operations - property name/value arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.lang", "System") and
    mc.getMethod().getName() in ["setProperty", "setProperties", "setSecurityManager", "exit"] and
    mc.getAnArgument() = sink.asExpr()
  ) or
  // Runtime operations - hook/status arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.lang", "Runtime") and
    mc.getMethod().getName() in ["addShutdownHook", "halt"] and
    mc.getAnArgument() = sink.asExpr()
  )
}

/**
 * Database operations - consistent argument identification.
 */
private predicate databaseOperationSink(DataFlow::Node sink) {
  // JDBC connection - URL/credentials arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.sql", "DriverManager") and
    mc.getMethod().getName() = "getConnection" and
    mc.getAnArgument() = sink.asExpr()
  ) or
  // SQL execution - SQL string arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getASourceSupertype*().hasQualifiedName("java.sql", "Statement") and
    mc.getMethod().getName().matches("execute%") and
    mc.getAnArgument() = sink.asExpr()
  )
}

/**
 * Security operations - consistent argument identification.
 */
private predicate securityOperationSink(DataFlow::Node sink) {
  // Access control - permission/action arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.security", "AccessController") and
    mc.getMethod().getName() in ["checkPermission", "doPrivileged", "doPrivilegedWithCombiner"] and
    mc.getAnArgument() = sink.asExpr()
  ) or
  // Policy operations - policy/permission arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.security", "Policy") and
    mc.getMethod().getName() in ["setPolicy", "getPermissions"] and
    mc.getAnArgument() = sink.asExpr()
  ) or
  // Security manager - permission arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getASourceSupertype*().hasQualifiedName("java.lang", "SecurityManager") and
    mc.getMethod().getName().matches("check%") and
    mc.getAnArgument() = sink.asExpr()
  )
}

/**
 * Reflection operations - consistent argument identification.
 */
private predicate reflectionOperationSink(DataFlow::Node sink) {
  // Class.forName - class name argument
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.lang", "Class") and
    mc.getMethod().getName() in ["forName", "newInstance"] and
    mc.getAnArgument() = sink.asExpr()
  ) or
  // ClassLoader operations - class name/bytes arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().getASourceSupertype*().hasQualifiedName("java.lang", "ClassLoader") and
    mc.getMethod().getName() in ["loadClass", "defineClass"] and
    mc.getAnArgument() = sink.asExpr()
  ) or
  // Reflection accessibility - boolean argument
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.lang.reflect", ["Method", "Field", "Constructor"]) and
    mc.getMethod().getName() = "setAccessible" and
    mc.getAnArgument() = sink.asExpr()
  ) or
  // Method invocation - target object and arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.lang.reflect", "Method") and
    mc.getMethod().getName() = "invoke" and
    mc.getAnArgument() = sink.asExpr()
  )
}

/**
 * Cryptographic operations - consistent argument identification.
 */
private predicate cryptographicOperationSink(DataFlow::Node sink) {
  // Cipher/KeyGenerator - algorithm/key arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("javax.crypto", ["Cipher", "KeyGenerator"]) and
    mc.getMethod().getName() in ["getInstance", "init", "generateKey"] and
    mc.getAnArgument() = sink.asExpr()
  ) or
  // Signature operations - algorithm/key arguments
  exists(MethodCall mc |
    mc.getMethod().getDeclaringType().hasQualifiedName("java.security", "Signature") and
    mc.getMethod().getName() in ["getInstance", "initSign", "initVerify"] and
    mc.getAnArgument() = sink.asExpr()
  )
}

/**
 * User-defined operations - NOW CONSISTENT with argument identification.
 */
private predicate highConfidenceUserDefinedSink(DataFlow::Node sink) {
  exists(MethodCall mc |
    // The sink must be an argument to the method call
    mc.getAnArgument() = sink.asExpr() and
    // Exclude standard Java packages
    not mc.getMethod().getDeclaringType().getPackage().getName().matches(["java.%", "javax.%", "sun.%", "com.sun.%"]) and
    (
      commandExecutionPattern(mc) or
      userManagementPattern(mc) or
      permissionRolePattern(mc) or
      databaseAdminPattern(mc) or
      passwordCredentialPattern(mc) or
      systemAdminPattern(mc)
    )
  )
}

/**
 * Command execution patterns - checks method name only.
 */
private predicate commandExecutionPattern(MethodCall mc) {
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:execut|run|invok|launch|start|call).*(?:command|cmd|process|script|shell|bash).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:command|cmd|process|script|shell|bash).*(?:execut|run|invok|launch|start|call).*") or
  (
    mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:execut|run|invok|perform|call).*") and
    exists(StringLiteral arg |
      arg = mc.getAnArgument().getAChildExpr*() and
      arg.getValue().toLowerCase().regexpMatch(".*(sudo|su|cmd|bash|sh|powershell|chmod|chown|rm|del|kill|ps).*")
    )
  )
}

/**
 * User management patterns - checks method name only.
 */
private predicate userManagementPattern(MethodCall mc) {
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:creat|add|insert|new).*(?:user|account|member|person).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:delet|remov|destroy|kill).*(?:user|account|member|person).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:updat|modif|chang|edit).*(?:user|account|member|person).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:user|account|member|person).*(?:creat|add|delet|remov|updat|modif).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:lock|unlock|enabl|disabl|activ|deactiv).*(?:user|account).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:user|account).*(?:lock|unlock|enabl|disabl|activ|deactiv).*")
}

/**
 * Permission/role patterns - checks method name only.
 */
private predicate permissionRolePattern(MethodCall mc) {
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:grant|assign|add|giv).*(?:permission|privil|right|access|role|author).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:revok|remov|delet|deny|block).*(?:permission|privil|right|access|role|author).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:permission|privil|right|access|role|author).*(?:grant|assign|revok|remov|add|giv|delet).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:elevat|promot|demot|upgrad|downgrad).*(?:user|role|privil|access).*") 
//   or
//   mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:check|verif|valid|test).*(?:permission|privil|right|access|role|author).*")
}

/**
 * Database admin patterns - checks method name AND arguments.
 */
private predicate databaseAdminPattern(MethodCall mc) {
  (
    mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:execut|run|perform|call).*(?:sql|query|statement).*") or
    mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:sql|query|statement).*(?:execut|run|perform|call).*")
  ) and
  exists(StringLiteral arg |
    arg = mc.getAnArgument().getAChildExpr*() and
    arg.getValue().toLowerCase().regexpMatch(".*(drop|create|alter|truncate|grant|revoke)\\s+.*")
  )
}

/**
 * Password/credential patterns - checks method name only.  
 * Fixed to exclude query/check methods and focus on actual operations.
 */
private predicate passwordCredentialPattern(MethodCall mc) {
  (
    // Password/credential modification operations
    mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:set|chang|updat|reset|modif|alter).*(?:password|passwd|pwd|credential|secret|key|token).*") or
    mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:password|passwd|pwd|credential|secret|key|token).*(?:set|chang|updat|reset|modif|alter).*") or
    
    // Password/credential generation operations
    mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:generat|creat|produc|make|build).*(?:password|passwd|pwd|credential|secret|key|token).*") or
    mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:password|passwd|pwd|credential|secret|key|token).*(?:generat|creat|produc|make|build).*") or
    
    // Cryptographic operations (actions only)
    mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:encrypt|decrypt|hash|unhash|sign|verify).*(?:password|passwd|pwd|credential|secret).*")
  ) and
  // Global exclusion - query verbs are never privileged operations
  not mc.getMethod().getName().toLowerCase().regexpMatch("^(is|has|can|check|verif|valid|test|get|read|load|fetch|retrieve).*")
}

/**
 * System/admin patterns - checks method name only.
 */
private predicate systemAdminPattern(MethodCall mc) {
    (
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:admin|administrat|manag|control|govern|supervis).*(?:system|server|service|resource).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:system|server|service|resource).*(?:admin|administrat|manag|control|govern|supervis).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:shutdown|restart|reboot|reload|refresh|stop|start|kill|terminat).*(?:system|server|service|process).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:backup|restor|recover|migrat|deploy|install|uninstall).*(?:system|database|service|application).*") or
  mc.getMethod().getName().toLowerCase().regexpMatch(".*(?:configur|setting|property).*(?:chang|updat|modif|set|reset).*")
  ) and
  // Global exclusion - query verbs are never privileged operations
  not mc.getMethod().getName().toLowerCase().regexpMatch("^(is|has|can|check|verif|valid|test|get|read|load|fetch|retrieve).*")

}

/**
 * Annotation-based operations - consistent argument identification.
 */
private predicate strongAnnotationBasedSink(DataFlow::Node sink) {
  exists(MethodCall mc, Annotation ann |
    mc.getAnArgument() = sink.asExpr() and
    ann = mc.getMethod().getAnAnnotation() and
    (
      ann.getType().hasQualifiedName("org.springframework.security.access.prepost", [
        "PreAuthorize", "PostAuthorize"
      ]) or
      ann.getType().hasQualifiedName("javax.annotation.security", [
        "RolesAllowed", "DenyAll", "RunAs"
      ]) or
      ann.getType().getName().toLowerCase() = "privileged"
    )
  )
}
