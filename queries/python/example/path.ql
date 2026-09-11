/**
 * @name Python Privilege Escalation Flow Analysis
 * @description Detects data flows from untrusted sources to privilege escalation sinks
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id neo
 * @tags security
 *       privilege-escalation
 *       data-flow
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking
import semmle.python.dataflow.new.RemoteFlowSources
import semmle.python.ApiGraphs
import libSources
import libOutBounds
import libSinks

/**
 * Predicate that matches execute_privileged_operation function calls with one parameter
 */
predicate executePrivilegedOperationCall( DataFlow::Node sink) {
  exists( DataFlow::CallCfgNode call | ((
    // Direct function call: execute_privileged_operation(sink)
    call.getFunction().toString() = "execute_privileged_operation"
    or
    // Method call: obj.execute_privileged_operation(sink)
    call.getFunction().(DataFlow::AttrRead).getAttributeName() = "execute_privileged_operation"
  ) and
  sink = call.getArg(0))
  )
}

/**
 * Configuration for privilege escalation taint tracking
 */
module MyConfig implements DataFlow::ConfigSig {
   predicate isSource(DataFlow::Node source) {
    source instanceof RemoteFlowSource
     or 
    enhanceRemoteSource(source)
   }

   predicate isSink(DataFlow::Node sink) {
   executePrivilegedOperationCall(sink)
   }


  // predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
  // //  outboundTaintStep(node1, node2)
  // }
}

module MyFlow = TaintTracking::Global<MyConfig>;
import MyFlow::PathGraph

from MyFlow::PathNode source, MyFlow::PathNode sink
where MyFlow::flowPath(source, sink)
select 
  sink.getNode(), 
  source, 
  sink, 
  "User input flows to  at $@",
  source.getNode(), 
  "user input source"