/**
 * @name JavaScript Class Definitions
 * @description Extract class definitions with field/method metadata.
 * @kind problem
 * @problem.severity info
 * @id javascript/class-definitions
 * @tags class-extraction
 */

import javascript

bindingset[relpath]
string dirOf(string relpath) { result = relpath.regexpReplaceAll("/[^/]+$", "") }

from ClassDefinition c, string name, string rel
where
  name = c.getName() and
  name != "" and
  rel = c.getLocation().getFile().getRelativePath() and
  rel.regexpMatch("(?i).*\\.(js|mjs|cjs|jsx|ts|tsx)$") and
  not rel.matches("%/node_modules/%") and
  not rel.matches("%/dist/%") and
  not rel.matches("%.min.js")
select c,
  // class_id|name|file|start|end|package|annotations|fields
  name + "@" + rel + ":" + c.getLocation().getStartLine().toString() +
  "|" + name +
  "|" + rel +
  "|" + c.getLocation().getStartLine().toString() +
  "|" + c.getLocation().getEndLine().toString() +
  "|" + dirOf(rel) +
  "|" +
  "|" + concat(string member |
      member = c.getAMethod().getName() or member = c.getField(_).getName()
    |
      member, ","
    )
