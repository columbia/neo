/**
 * @name Go Function Definitions
 * @description Extract all function/method definitions with metadata
 * @kind problem
 * @problem.severity info
 * @id go/function-definitions
 * @tags function-extraction
 */

import go

/**
 * Get the receiver base type name for a method (MethodDecl), or "" for free functions.
 * Uses MethodDecl subclass — getReceiverBaseTypeName() does not exist on FuncDecl directly.
 */
string receiverTypeName(FuncDecl fd) {
  result = fd.(MethodDecl).getReceiverBaseType().getName()
  or
  not fd instanceof MethodDecl and result = ""
}

from Function func
where
  // Only functions with source declarations
  exists(func.getFuncDecl()) and
  // Only source .go files — exclude vendor and generated code
  func.getFuncDecl().getFile().getRelativePath().matches("%.go") and
  not func.getFuncDecl().getFile().getRelativePath().matches("%/vendor/%") and
  not func.getFuncDecl().getFile().getRelativePath().matches("%/.git/%") and
  // Must have a name
  func.getName().length() > 0 and
  // Exclude blank identifier
  func.getName() != "_"
select
  func.getFuncDecl(),
  // Pipe-delimited: function_id|name|file|start|end|signature|class|package|annotations
  // Use getFuncDecl().getLocation() throughout for consistency (not func.getLocation()).
  func.getName() + "@" +
  func.getFuncDecl().getFile().getRelativePath() + ":" +
  func.getFuncDecl().getLocation().getStartLine().toString() +
  "|" + func.getName() +
  "|" + func.getFuncDecl().getFile().getRelativePath() +
  "|" + func.getFuncDecl().getLocation().getStartLine().toString() +
  "|" + func.getFuncDecl().getLocation().getEndLine().toString() +
  "|" + "func " + func.getName() +
  "|" + receiverTypeName(func.getFuncDecl()) +
  "|" + func.getPackage().getName() +
  "|"
