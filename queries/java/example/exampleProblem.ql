/**
 * @name HTTP Entry Point Sources  
 * @description Identifies parameters of HTTP entry point methods (not internal usage)
 * @kind problem
 * @problem.severity info
 * @precision high
 * @id java/http-entry-point-sources
 * @tags security
 *       sources
 *       entry-points
 */

import java
import semmle.code.java.dataflow.DataFlow
import semmle.code.java.dataflow.TaintTracking
import semmle.code.java.dataflow.FlowSources
import libSources
import libOutBounds
import libChecks

from Element element, string location, string checkType, string description
where isAnyPermissionCheck(element, location, checkType, description)
select element, checkType + ": " + description + " " + location