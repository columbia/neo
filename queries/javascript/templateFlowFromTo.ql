/**
 * @name Qflow: taint from a named source to a named sink
 * @description Parameterised intra-service flow query. {{FROM}} / {{TO}} are
 *              filled with CodeQL regexes by src/genquery/gen_flowfromto.py.
 * @kind path-problem
 * @problem.severity info
 * @id neo/qflow
 */

import javascript
import semmle.javascript.dataflow.TaintTracking

predicate fromSpec(DataFlow::Node n) {
  exists(DataFlow::CallNode c | c.getCalleeName().regexpMatch("{{FROM}}") and n = c)
  or
  exists(VarAccess va | va.getName().regexpMatch("{{FROM}}") and n = va.flow())
  or
  exists(Parameter p | p.getName().regexpMatch("{{FROM}}") and n = DataFlow::parameterNode(p))
  or
  "{{FROM}}".toLowerCase()
      .regexpMatch(".*(request|user|input|source|param|remote|body|query|form).*") and
  n instanceof RemoteFlowSource
}

predicate toSpec(DataFlow::Node n) {
  exists(DataFlow::InvokeNode c | c.getCalleeName().regexpMatch("{{TO}}") and n = c.getAnArgument())
}

module Cfg implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) { fromSpec(n) }

  predicate isSink(DataFlow::Node n) { toSpec(n) }
}

module Flow = TaintTracking::Global<Cfg>;

import Flow::PathGraph

from Flow::PathNode source, Flow::PathNode sink
where Flow::flowPath(source, sink)
select sink.getNode(), source, sink, "QFLOW|{{FROM}}|{{TO}}"
