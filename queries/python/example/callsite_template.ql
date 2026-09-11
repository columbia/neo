/**
 * @name Python function calls matching regex patterns
 * @description Detects Python function calls where the function name matches specified regex patterns
 * @kind problem
 * @problem.severity warning
 * @id python/function-calls-regex-patterns
 */

import python

/**
 * Predicate to match function calls based on regex patterns
 */
private predicate matchesPatterns(Call call) {
  exists(string name |
    (
      name = call.getFunc().(Name).getId().toLowerCase() or
      name = call.getFunc().(Attribute).getName().toLowerCase()
    ) and
    ({{REGEX_PATTERNS}})
  )
}

/**
 * Main query: Find all function calls matching the patterns
 */
from Call call
where matchesPatterns(call)
select call, 
       "Function call matches pattern"