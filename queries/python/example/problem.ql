/**
 * @name Python Privilege Escalation Flow Analysis
 * @description Detects data flows from untrusted sources to privilege escalation sinks
 * @kind problem
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

// /**
//  * Configuration for privilege escalation taint tracking
//  */
// module MyConfig implements DataFlow::ConfigSig {
//    predicate isSource(DataFlow::Node source) {
//     source instanceof RemoteFlowSource
//     or 
//     additionalRemoteSource(source)
//    }

//    predicate isSink(DataFlow::Node sink) {
//    outBoundSink(sink)
//    }


//   predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
//    none()
//   }
// }

// module MyFlow = TaintTracking::Global<MyConfig>;
// import MyFlow::PathGraph

from  Call call
where call.getFunc().toString() = "execute_privileged_operation"
select call, "sinks"

// Main query - focuses on actual library usage
// // Query to show taint flow paths
// from DataFlow::Node source, DataFlow::Node sink
// where outboundTaintStep(source, sink)
// select sink,
//   "Outbound data transmission of user input from "