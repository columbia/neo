import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.ApiGraphs

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
  // or
  // cryptographicOperationSink(sink)
  or
  highConfidenceUserDefinedSink(sink)
}

/**
 * File system operations - consistent argument identification.
 */
predicate fileSystemSink(DataFlow::Node sink) {
  // Built-in file operations
  exists(DataFlow::CallCfgNode call |
    call = API::builtin("open").getACall() and
    sink = call.getArg(0)
  )
  or
  // os module file operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("os").getMember(["remove", "unlink", "rmdir", "mkdir", "makedirs", "rename", "chmod", "chown"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // shutil operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("shutil").getMember(["rmtree", "move", "copy", "copy2", "copytree", "chown"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // pathlib operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("pathlib").getMember("Path").getReturn().getMember(["unlink", "rmdir", "mkdir", "chmod", "rename", "replace"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // tempfile operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("tempfile").getMember(["mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryDirectory"]).getACall() and
    sink = call.getArgByName("dir")
  )
}

/**
 * Process execution operations - consistent argument identification.
 */
predicate processExecutionSink(DataFlow::Node sink) {
  // subprocess module
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("subprocess").getMember(["run", "call", "check_call", "check_output", "Popen"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // os.system and os.exec* family
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("os").getMember(["system", "execl", "execle", "execlp", "execv", "execve", "execvp", "execvpe", "spawnl", "spawnle", "spawnlp", "spawnv", "spawnve", "spawnvp", "spawnvpe"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // os.popen
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("os").getMember("popen").getACall() and
    sink = call.getArg(0)
  )
  or
  // commands module (deprecated but still used)
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("commands").getMember(["getoutput", "getstatusoutput"]).getACall() and
    sink = call.getArg(0)
  )
}

/**
 * Network operations - consistent argument identification.
 */
predicate networkOperationSink(DataFlow::Node sink) {
  // socket operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("socket").getMember("socket").getReturn().getMember(["connect", "connect_ex", "bind"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // urllib operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("urllib.request").getMember(["urlopen", "urlretrieve"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // ftplib operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("ftplib").getMember("FTP").getReturn().getMember(["connect", "login"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // smtplib operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("smtplib").getMember("SMTP").getReturn().getMember(["connect", "login"]).getACall() and
    sink = call.getArg(0)
  )
}

/**
 * System configuration - consistent argument identification.
 */
predicate systemConfigSink(DataFlow::Node sink) {
  // os.environ modifications
  exists(Subscript sub |
    sub.getObject().(Attribute).getName() = "environ" and
    sub.getObject().(Attribute).getObject().(Name).getId() = "os" and
    sink.asExpr() = sub.getIndex()
  )
  or
  // os.putenv
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("os").getMember("putenv").getACall() and
    sink in [call.getArg(0), call.getArg(1)]
  )
  or
  // sys.exit
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("sys").getMember("exit").getACall() and
    sink = call.getArg(0)
  )
  or
  // signal handling
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("signal").getMember(["signal", "alarm"]).getACall() and
    sink = call.getArg(0)
  )
}

/**
 * Database operations - consistent argument identification.
 */
predicate databaseOperationSink(DataFlow::Node sink) {
  // sqlite3 operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("sqlite3").getMember(["connect", "execute", "executemany", "executescript"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // psycopg2 (PostgreSQL)
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("psycopg2").getMember("connect").getACall() and
    sink = call.getArgByName(["host", "database", "user", "password"])
  )
  or
  // pymongo operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("pymongo").getMember("MongoClient").getACall() and
    sink = call.getArg(0)
  )
  or
  // mysql.connector
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("mysql.connector").getMember("connect").getACall() and
    sink = call.getArgByName(["host", "database", "user", "password"])
  )
  or
  // SQL execution patterns
  exists(Call call, Attribute attr |
    call.getFunc() = attr and
    attr.getName() in ["execute", "executemany", "executescript"] and
    sink.asExpr() = call.getArg(0)
  )
}

/**
 * Security operations - consistent argument identification.
 */
predicate securityOperationSink(DataFlow::Node sink) {
  // Authentication operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("getpass").getMember("getpass").getACall() and
    sink = call.getArg(0)
  )
  or
  // SSL/TLS operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("ssl").getMember(["create_default_context", "SSLContext"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // JWT operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("jwt").getMember(["encode", "decode"]).getACall() and
    sink in [call.getArg(0), call.getArg(1)]
  )
  or
  // Cryptography library
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("cryptography.fernet").getMember("Fernet").getReturn().getMember(["encrypt", "decrypt"]).getACall() and
    sink = call.getArg(0)
  )
}

/**
 * Reflection operations - consistent argument identification.
 */
predicate reflectionOperationSink(DataFlow::Node sink) {
  // Dynamic imports
  exists(DataFlow::CallCfgNode call |
    call = API::builtin("__import__").getACall() and
    sink = call.getArg(0)
  )
  or
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("importlib").getMember("import_module").getACall() and
    sink = call.getArg(0)
  )
  or
  // eval and exec
  exists(DataFlow::CallCfgNode call |
    call = API::builtin(["eval", "exec", "compile"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // getattr, setattr, delattr
  exists(DataFlow::CallCfgNode call |
    call = API::builtin(["getattr", "setattr", "delattr", "hasattr"]).getACall() and
    sink = call.getArg(1)
  )
  or
  // globals and locals manipulation
  exists(DataFlow::CallCfgNode call |
    call = API::builtin(["globals", "locals", "vars"]).getACall() and
    sink = call.getArg(0)
  )
}

/**
 * Cryptographic operations - consistent argument identification.
 */
predicate cryptographicOperationSink(DataFlow::Node sink) {
  // hashlib operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("hashlib").getMember(["md5", "sha1", "sha256", "sha512", "new"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // hmac operations
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("hmac").getMember(["new", "digest"]).getACall() and
    sink in [call.getArg(0), call.getArg(1)]
  )
  or
  // secrets module
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("secrets").getMember(["token_bytes", "token_hex", "token_urlsafe"]).getACall() and
    sink = call.getArg(0)
  )
  or
  // PyCrypto/PyCryptodome
  exists(DataFlow::CallCfgNode call |
    call = API::moduleImport("Crypto.Cipher").getMember(_).getMember("new").getACall() and
    sink in [call.getArg(0), call.getArg(1)]
  )
}

/**
 * User-defined operations - consistent with argument identification.
 */
predicate highConfidenceUserDefinedSink(DataFlow::Node sink) {
  exists(Call call |
    sink.asExpr() = call.getAnArg() and
    not call.getFunc().(Attribute).getObject().(Name).getId() in ["os", "sys", "subprocess", "socket", "ssl", "hashlib", "hmac", "sqlite3", "psycopg2", "pymongo"] and
    (
      commandExecutionPattern(call) or
      userManagementPattern(call) or
      permissionRolePattern(call) or
      databaseAdminPattern(call) or
      passwordCredentialPattern(call) or
      systemAdminPattern(call)
    )
  )
}

/**
 * Command execution patterns - checks method name only.
 */
predicate commandExecutionPattern(Call call) {
  exists(string name |
    name = call.getFunc().(Attribute).getName().toLowerCase() and
    (
      name.regexpMatch(".*(?:execut|run|invok|launch|start|call).*(?:command|cmd|process|script|shell|bash).*") or
      name.regexpMatch(".*(?:command|cmd|process|script|shell|bash).*(?:execut|run|invok|launch|start|call).*") or
      (
        name.regexpMatch(".*(?:execut|run|invok|perform|call).*") and
        exists(StringLiteral arg |
          arg = call.getAnArg() and
          arg.getText().toLowerCase().regexpMatch(".*(sudo|su|cmd|bash|sh|powershell|chmod|chown|rm|del|kill|ps).*")
        )
      )
    )
  )
}

/**
 * User management patterns - checks method name only.
 */
predicate userManagementPattern(Call call) {
  exists(string name |
    name = call.getFunc().(Attribute).getName().toLowerCase() and
    (
      name.regexpMatch(".*(?:creat|add|insert|new).*(?:user|account|member|person).*") or
      name.regexpMatch(".*(?:delet|remov|destroy|kill).*(?:user|account|member|person).*") or
      name.regexpMatch(".*(?:updat|modif|chang|edit).*(?:user|account|member|person).*") or
      name.regexpMatch(".*(?:user|account|member|person).*(?:creat|add|delet|remov|updat|modif).*") or
      name.regexpMatch(".*(?:lock|unlock|enabl|disabl|activ|deactiv).*(?:user|account).*") or
      name.regexpMatch(".*(?:user|account).*(?:lock|unlock|enabl|disabl|activ|deactiv).*")
    )
  )
}

/**
 * Permission/role patterns - checks method name only.
 */
predicate permissionRolePattern(Call call) {
  exists(string name |
    name = call.getFunc().(Attribute).getName().toLowerCase() and
    (
      name.regexpMatch(".*(?:grant|assign|add|giv).*(?:permission|privil|right|access|role|author).*") or
      name.regexpMatch(".*(?:revok|remov|delet|deny|block).*(?:permission|privil|right|access|role|author).*") or
      name.regexpMatch(".*(?:permission|privil|right|access|role|author).*(?:grant|assign|revok|remov|add|giv|delet).*") or
      name.regexpMatch(".*(?:elevat|promot|demot|upgrad|downgrad).*(?:user|role|privil|access).*")
    )
  )
}

/**
 * Database admin patterns - checks method name AND arguments.
 */
predicate databaseAdminPattern(Call call) {
  exists(string name |
    name = call.getFunc().(Attribute).getName().toLowerCase() and
    (
      name.regexpMatch(".*(?:execut|run|perform|call).*(?:sql|query|statement).*") or
      name.regexpMatch(".*(?:sql|query|statement).*(?:execut|run|perform|call).*")
    ) and
    exists(StringLiteral arg |
      arg = call.getAnArg() and
      arg.getText().toLowerCase().regexpMatch(".*(drop|create|alter|truncate|grant|revoke)\\s+.*")
    )
  )
}

/**
 * Password/credential patterns - checks method name only.
 */
predicate passwordCredentialPattern(Call call) {
  exists(string name |
    name = call.getFunc().(Attribute).getName().toLowerCase() and
    (
      name.regexpMatch(".*(?:set|chang|updat|reset|modif|alter).*(?:password|passwd|pwd|credential|secret|key|token).*") or
      name.regexpMatch(".*(?:password|passwd|pwd|credential|secret|key|token).*(?:set|chang|updat|reset|modif|alter).*") or
      name.regexpMatch(".*(?:generat|creat|produc|make|build).*(?:password|passwd|pwd|credential|secret|key|token).*") or
      name.regexpMatch(".*(?:password|passwd|pwd|credential|secret|key|token).*(?:generat|creat|produc|make|build).*") or
      name.regexpMatch(".*(?:encrypt|decrypt|hash|unhash|sign|verify).*(?:password|passwd|pwd|credential|secret).*")
    ) and
    not name.regexpMatch("^(is|has|can|check|verif|valid|test|get|read|load|fetch|retrieve).*")
  )
}

/**
 * System/admin patterns - checks method name only.
 */
predicate systemAdminPattern(Call call) {
  exists(string name |
    name = call.getFunc().(Attribute).getName().toLowerCase() and
    (
      name.regexpMatch(".*(?:admin|administrat|manag|control|govern|supervis).*(?:system|server|service|resource).*") or
      name.regexpMatch(".*(?:system|server|service|resource).*(?:admin|administrat|manag|control|govern|supervis).*") or
      name.regexpMatch(".*(?:shutdown|restart|reboot|reload|refresh|stop|start|kill|terminat).*(?:system|server|service|process).*") or
      name.regexpMatch(".*(?:backup|restor|recover|migrat|deploy|install|uninstall).*(?:system|database|service|application).*") or
      name.regexpMatch(".*(?:configur|setting|property).*(?:chang|updat|modif|set|reset).*")
    ) and
    not name.regexpMatch("^(is|has|can|check|verif|valid|test|get|read|load|fetch|retrieve).*")
  )
}

/**
 * Gets the privileged operation category.
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
  securityOperationSink(sink) and result = "SECURITY_OPERATION"
  or
  reflectionOperationSink(sink) and result = "REFLECTION_OPERATION"
  or
  cryptographicOperationSink(sink) and result = "CRYPTOGRAPHIC_OPERATION"
  or
  highConfidenceUserDefinedSink(sink) and result = "USER_DEFINED"
}