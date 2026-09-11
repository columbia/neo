import go
import semmle.go.dataflow.DataFlow

/**
 * Enhanced privileged operations sink.
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
  reflectionOperationSink(sink)
  or
  cryptographicOperationSink(sink)
  or
  highConfidenceUserDefinedSink(sink)
}

/**
 * File system operations.
 */
predicate fileSystemSink(DataFlow::Node sink) {
  // os package file operations
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("os", 
      ["Open", "OpenFile", "Create", "Remove", "RemoveAll", "Rename", "Mkdir", 
       "MkdirAll", "Chmod", "Chown", "Lchown"]) and
    sink = call.getAnArgument()
  )
  or
  // io/ioutil file operations (deprecated but still used)
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("io/ioutil", 
      ["ReadFile", "WriteFile", "ReadDir"]) and
    sink = call.getArgument(0)
  )
  or
  // os.File method calls
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("os", "File", 
      ["Write", "WriteString", "WriteAt", "Chmod", "Chown"]) and
    sink = call.getAnArgument()
  )
}

/**
 * Process execution operations.
 */
predicate processExecutionSink(DataFlow::Node sink) {
  // os/exec.Command
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("os/exec", "Command") and
    sink = call.getAnArgument()
  )
  or
  // exec.Cmd methods
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("os/exec", "Cmd", 
      ["Start", "Run", "CombinedOutput", "Output"]) and
    sink = call.getReceiver()
  )
}

/**
 * Network operations.
 */
predicate networkOperationSink(DataFlow::Node sink) {
  // net.Dial family
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("net", 
      ["Dial", "DialTimeout", "DialTCP", "DialUDP", "DialIP", "Listen", 
       "ListenTCP", "ListenUDP", "ListenIP"]) and
    sink = call.getAnArgument()
  )
  or
  // net/http server
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("net/http", 
      ["ListenAndServe", "ListenAndServeTLS", "Serve", "ServeTLS"]) and
    sink = call.getAnArgument()
  )
}

/**
 * System configuration.
 */
predicate systemConfigSink(DataFlow::Node sink) {
  // os.Setenv
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("os", "Setenv") and
    sink = call.getAnArgument()
  )
  or
  // os.Exit
  exists(DataFlow::CallNode call |
    call.getTarget().hasQualifiedName("os", "Exit") and
    sink = call.getArgument(0)
  )
}

/**
 * Database operations.
 */
predicate databaseOperationSink(DataFlow::Node sink) {
  // database/sql non-Context operations (query string is arg 0)
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("database/sql", "DB",
      ["Exec", "Query", "QueryRow", "Prepare"]) and
    sink = call.getArgument(0)
  )
  or
  // database/sql *Context operations (ctx is arg 0, query string is arg 1)
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("database/sql", "DB",
      ["ExecContext", "QueryContext", "QueryRowContext", "PrepareContext"]) and
    sink = call.getArgument(1)
  )
  or
  // Redis operations
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("github.com/redis/go-redis/v9", "Client", 
      ["Set", "HSet", "LPush", "RPush", "SAdd", "ZAdd", "Eval"]) and
    sink = call.getAnArgument()
  )
}

/**
 * Reflection operations.
 */
predicate reflectionOperationSink(DataFlow::Node sink) {
  // reflect.ValueOf operations that can modify state
  exists(DataFlow::MethodCallNode call |
    call.getTarget().hasQualifiedName("reflect", "Value", 
      ["Set", "SetBool", "SetInt", "SetString", "SetFloat", "SetBytes", "SetCap", 
       "SetLen", "SetMapIndex", "SetPointer"]) and
    sink = call.getAnArgument()
  )
}

/**
 * Cryptographic operations.
 */
predicate cryptographicOperationSink(DataFlow::Node sink) {
  // crypto hash operations
  exists(DataFlow::CallNode call |
    (
      call.getTarget().hasQualifiedName("crypto/md5", "New") or
      call.getTarget().hasQualifiedName("crypto/sha1", "New") or
      call.getTarget().hasQualifiedName("crypto/sha256", ["New", "New224"]) or
      call.getTarget().hasQualifiedName("crypto/sha512", ["New", "New384"])
    ) and
    sink = call.getResult()
  )
}

/**
 * User-defined privileged operations.
 */
predicate highConfidenceUserDefinedSink(DataFlow::Node sink) {
  exists(DataFlow::CallNode call, Function f |
    call.getTarget() = f and
    sink = call.getAnArgument() and
    // Exclude standard library functions
    not exists(f.getPackage().getPath()) and
    (
      commandExecutionPattern(f) or
      userManagementPattern(f) or
      permissionRolePattern(f) or
      databaseAdminPattern(f) or
      passwordCredentialPattern(f) or
      systemAdminPattern(f)
    )
  )
}

/**
 * Command execution patterns.
 */
predicate commandExecutionPattern(Function f) {
  f.getName().regexpMatch("(?i).*(execute|run|invoke|launch|start|call).*(command|cmd|process|script|shell|bash).*") or
  f.getName().regexpMatch("(?i).*(command|cmd|process|script|shell|bash).*(execute|run|invoke|launch|start|call).*")
}

/**
 * User management patterns.
 */
predicate userManagementPattern(Function f) {
  f.getName().regexpMatch("(?i).*(create|add|insert|new|delete|remove|destroy|update|modify|change|edit).*(user|account|member).*") or
  f.getName().regexpMatch("(?i).*(user|account|member).*(create|add|delete|remove|update|modify).*") or
  f.getName().regexpMatch("(?i).*(lock|unlock|enable|disable|activate|deactivate).*(user|account).*")
}

/**
 * Permission/role patterns.
 */
predicate permissionRolePattern(Function f) {
  f.getName().regexpMatch("(?i).*(grant|assign|add|give|revoke|remove|delete|deny).*(permission|privilege|right|access|role|authority).*") or
  f.getName().regexpMatch("(?i).*(permission|privilege|right|access|role|authority).*(grant|assign|revoke|remove|add).*") or
  f.getName().regexpMatch("(?i).*(elevate|promote|demote|upgrade|downgrade).*(user|role|privilege|access).*")
}

/**
 * Database admin patterns.
 */
predicate databaseAdminPattern(Function f) {
  f.getName().regexpMatch("(?i).*(execute|run|perform|call).*(sql|query|statement).*") or
  f.getName().regexpMatch("(?i).*(sql|query|statement).*(execute|run|perform|call).*")
}

/**
 * Password/credential patterns.
 */
predicate passwordCredentialPattern(Function f) {
  (
    f.getName().regexpMatch("(?i).*(set|change|update|reset|modify|alter).*(password|passwd|pwd|credential|secret|key|token).*") or
    f.getName().regexpMatch("(?i).*(password|passwd|pwd|credential|secret|key|token).*(set|change|update|reset|modify|alter).*") or
    f.getName().regexpMatch("(?i).*(generate|create|produce|make|build).*(password|passwd|pwd|credential|secret|key|token).*") or
    f.getName().regexpMatch("(?i).*(password|passwd|pwd|credential|secret|key|token).*(generate|create|produce|make|build).*") or
    f.getName().regexpMatch("(?i).*(encrypt|decrypt|hash|unhash|sign|verify).*(password|passwd|pwd|credential|secret).*")
  ) and
  not f.getName().regexpMatch("^(?i)(is|has|can|check|verify|valid|test|get|read|load|fetch|retrieve).*")
}

/**
 * System/admin patterns.
 */
predicate systemAdminPattern(Function f) {
  (
    f.getName().regexpMatch("(?i).*(admin|administrate|manage|control|govern|supervise).*(system|server|service|resource).*") or
    f.getName().regexpMatch("(?i).*(system|server|service|resource).*(admin|administrate|manage|control|govern|supervise).*") or
    f.getName().regexpMatch("(?i).*(shutdown|restart|reboot|reload|refresh|stop|start|kill|terminate).*(system|server|service|process).*") or
    f.getName().regexpMatch("(?i).*(backup|restore|recover|migrate|deploy|install|uninstall).*(system|database|service|application).*") or
    f.getName().regexpMatch("(?i).*(configure|setting|property).*(change|update|modify|set|reset).*")
  ) and
  not f.getName().regexpMatch("^(?i)(is|has|can|check|verify|valid|test|get|read|load|fetch|retrieve).*")
}

/**
 * Gets the privileged sink category.
 */
string getPrivilegedSinkCategory(DataFlow::Node sink) {
  fileSystemSink(sink) and result = "FILE_SYSTEM"
  or
  processExecutionSink(sink) and result = "PROCESS_EXECUTION"
  or
  networkOperationSink(sink) and result = "NETWORK_OPERATION"
  or
  systemConfigSink(sink) and result = "SYSTEM_CONFIG"
  or
  databaseOperationSink(sink) and result = "DATABASE_OPERATION"
  or
  reflectionOperationSink(sink) and result = "REFLECTION_OPERATION"
  or
  cryptographicOperationSink(sink) and result = "CRYPTOGRAPHIC_OPERATION"
  or
  highConfidenceUserDefinedSink(sink) and result = "USER_DEFINED"
}