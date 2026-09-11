/**
 * @name Qflow: taint from a named source to a named sink
 * @description Parameterised intra-service flow query. {{FROM}} / {{TO}} are
 *              filled with CodeQL regexes by src/genquery/gen_flowfromto.py.
 * @kind path-problem
 * @problem.severity info
 * @id neo/qflow
 */

import cpp
import semmle.code.cpp.dataflow.new.TaintTracking
import libStringTaint

predicate fromSpec(DataFlow::Node n) {
  exists(FunctionCall fc | fc.getTarget().getName().regexpMatch("{{FROM}}") and n.asExpr() = fc)
  or
  exists(VariableAccess va | va.getTarget().getName().regexpMatch("{{FROM}}") and n.asExpr() = va)
  or
  exists(Parameter p | p.getName().regexpMatch("{{FROM}}") and n.asParameter() = p)
}

predicate toSpec(DataFlow::Node n) {
  exists(FunctionCall fc |
    fc.getTarget().getName().regexpMatch("{{TO}}") and fc.getAnArgument() = n.asExpr()
  )
}

module Cfg implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) { fromSpec(n) }

  predicate isSink(DataFlow::Node n) { toSpec(n) }

  predicate isAdditionalFlowStep(DataFlow::Node n1, DataFlow::Node n2) {
    cppStringTaintStep(n1, n2)
  }
}

module Flow = TaintTracking::Global<Cfg>;

import Flow::PathGraph

from Flow::PathNode source, Flow::PathNode sink
where Flow::flowPath(source, sink)
select sink.getNode(), source, sink, "QFLOW|{{FROM}}|{{TO}}"
