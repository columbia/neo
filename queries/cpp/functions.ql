/**
 * @name C++ Function Definitions
 * @description Extract all function/method definitions with metadata
 * @kind problem
 * @problem.severity info
 * @id cpp/function-definitions
 * @tags function-extraction
 */

import cpp

/**
 * Get the enclosing class name for a member function, or "" for free functions.
 */
string enclosingClass(Function func) {
  not isLambdaCallOperator(func) and result = func.(MemberFunction).getDeclaringType().getName()
  or
  not func instanceof MemberFunction and result = ""
  or
  isLambdaCallOperator(func) and result = ""
}

/** Is *func* a lambda's call operator (its declaring type is the compiler's
 *  synthetic closure class, named like "lambda [] type at line …")? */
predicate isLambdaCallOperator(Function func) {
  func.getName() = "operator()" and
  func.(MemberFunction).getDeclaringType().getName().matches("lambda %")
}

/** Real name, or "anonymous" for a lambda's call operator -- route handlers
 *  and callbacks are routinely passed as inline lambdas (paper-relevant:
 *  that's how every cpp-httplib/Crow endpoint and most STL-algorithm
 *  callbacks are written), and they'd otherwise be excluded by the
 *  operator-overload filter below along with genuine operator overloads. */
string fnName(Function func) {
  isLambdaCallOperator(func) and result = "anonymous"
  or
  not isLambdaCallOperator(func) and result = func.getName()
}

/**
 * Get the namespace name for a function, or "" for global namespace.
 * For member functions, use the declaring type's namespace.
 * For free functions, use the function's enclosing namespace.
 */
string namespaceName(Function func) {
  exists(Namespace ns |
    (
      func instanceof MemberFunction and
      func.(MemberFunction).getDeclaringType().getNamespace() = ns
      or
      not func instanceof MemberFunction and
      func.getNamespace() = ns
    ) and
    not ns instanceof GlobalNamespace and
    result = ns.getQualifiedName()
  )
  or
  (
    not exists(Namespace ns |
      (
        func instanceof MemberFunction and
        func.(MemberFunction).getDeclaringType().getNamespace() = ns
        or
        not func instanceof MemberFunction and
        func.getNamespace() = ns
      ) and
      not ns instanceof GlobalNamespace
    ) and
    result = ""
  )
}

from Function func
where
  // Exclude compiler-generated functions
  not func.isCompilerGenerated() and
  // Exclude system/library headers
  not func.getFile().getAbsolutePath().matches("%/usr/include/%") and
  not func.getFile().getAbsolutePath().matches("%/include/c++/%") and
  not func.getFile().getAbsolutePath().matches("%/mingw%/include/%") and
  not func.getFile().getAbsolutePath().matches("%/MSVC/%/include/%") and
  not func.getFile().getAbsolutePath().matches("%/Windows Kits/%/Include/%") and
  // Exclude common test framework internals
  not func.getFile().getRelativePath().matches("%gtest%") and
  not func.getFile().getRelativePath().matches("%catch%") and
  // Source extensions only
  (
    func.getFile().getExtension() = "cpp" or
    func.getFile().getExtension() = "cc" or
    func.getFile().getExtension() = "cxx" or
    func.getFile().getExtension() = "c" or
    func.getFile().getExtension() = "h" or
    func.getFile().getExtension() = "hpp" or
    func.getFile().getExtension() = "hxx"
  ) and
  // Must have a valid location
  exists(func.getLocation().getFile()) and
  // Must have a real name
  func.getName().length() > 0 and
  not func.getName().matches("%<anonymous>%") and
  // Exclude operator overloads, except a lambda's call operator -- route
  // handlers and STL-algorithm callbacks are routinely inline lambdas, and
  // excluding them left every such handler out of the call graph.
  (not func.getName().matches("operator%") or isLambdaCallOperator(func))
select
  func,
  // Pipe-delimited: function_id|name|file|start|end|signature|class|namespace|annotations
  fnName(func) + "@" +
  func.getFile().getRelativePath() + ":" +
  func.getLocation().getStartLine().toString() +
  "|" + fnName(func) +
  "|" + func.getFile().getRelativePath() +
  "|" + func.getLocation().getStartLine().toString() +
  "|" + func.getLocation().getEndLine().toString() +
  "|" + func.getType().getName() + " " + fnName(func) + "(" + func.getParameterString() + ")" +
  "|" + enclosingClass(func) +
  "|" + namespaceName(func) +
  "|"
