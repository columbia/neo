/**
 * @name Inter-service outbound calls and channel identifiers (Qinter)
 * @description libcurl / cpr / cpp-httplib / Boost.Beast outbound requests
 *              with the constant URL. Best-effort; the Python heuristic
 *              extractor is the fallback.
 * @kind problem
 * @problem.severity info
 * @id neo/interservice-out
 */

import cpp

/** String value of an expression: a literal, `operator+`/`+=` folded (keeping
 *  the constant prefix when the tail is a runtime value), or a variable
 *  reached through its initialiser. */
string strValue(Expr e) {
  result = e.(StringLiteral).getValue()
  or
  // the compiler's implicit `std::string(const char*)` wrapper around a literal
  exists(ConstructorCall cc | cc = e and cc.getTarget().getDeclaringType().getName().matches("basic_string%") |
    result = strValue(cc.getArgument(0))
  )
  or
  exists(Call c | c = e and c.getTarget().getName() = ["operator+", "operator+="] |
    result = strValue(c.getArgument(0)) + strValue(c.getArgument(1))
    or
    result = strValue(c.getArgument(0))
  )
  or
  exists(Variable v | e = v.getAnAccess() | result = strValue(v.getInitializer().getExpr()))
}

/** A method call on an HTTP-client-shaped object: httplib::Client and similar
 *  `Client cli(...); cli.Get(path)` wrappers. */
predicate onHttpClientType(FunctionCall call) {
  exists(Expr q | q = call.getQualifier() |
    q.getType().getName().matches(["%Client%", "%Session%"])
  )
}

string constUrlArg(FunctionCall call) {
  exists(Expr e | e = call.getAnArgument() | result = strValue(e))
}

predicate outboundCall(FunctionCall call, string proto, string verb) {
  exists(string n | n = call.getTarget().getName() |
    n.toLowerCase().matches("%curl_easy_setopt%") and proto = "http" and verb = ""
    or
    n.toLowerCase().matches("%curl_easy_perform%") and proto = "http" and verb = ""
    or
    // cpr::Get / cpr::Post / ...
    n in ["Get", "Post", "Put", "Delete", "Patch", "Head"] and
    call.getTarget().getNamespace().getName() = "cpr" and
    proto = "http" and
    verb = n.toUpperCase()
    or
    // httplib::Client / similar: cli.Get(path), cli.Post(path, body, type)
    n in ["Get", "Post", "Put", "Delete", "Patch", "Head"] and
    onHttpClientType(call) and
    proto = "http" and
    verb = n.toUpperCase()
  )
}

string enclosing(FunctionCall call) {
  exists(Function f | f = call.getEnclosingFunction() |
    result =
      f.getName() + "@" + call.getFile().getRelativePath() + ":" +
        f.getLocation().getStartLine().toString()
  )
}

from FunctionCall call, string proto, string verb, string channel
where outboundCall(call, proto, verb) and channel = constUrlArg(call) and channel.matches(["http%", "/%"])
select call,
  "INTER|" + proto + "|" + verb + "|" + channel + "|" +
    call.getFile().getRelativePath() + ":" + call.getLocation().getStartLine().toString() + "|" +
    enclosing(call)
