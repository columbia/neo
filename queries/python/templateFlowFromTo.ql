/**
 * @name Qflow: taint from a named source to a named sink
 * @description Parameterised intra-service flow query. {{FROM}} / {{TO}} are
 *              filled with CodeQL regexes by src/genquery/gen_flowfromto.py.
 * @kind path-problem
 * @problem.severity info
 * @id neo/qflow
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking
import semmle.python.dataflow.new.RemoteFlowSources

predicate fromSpec(DataFlow::Node n) {
  exists(Call c, Name f |
    c.getFunc() = f and f.getId().regexpMatch("{{FROM}}") and n.asExpr() = c
  )
  or
  exists(Call c, Attribute a |
    c.getFunc() = a and a.getName().regexpMatch("{{FROM}}") and n.asExpr() = c
  )
  or
  exists(Name v | v.getId().regexpMatch("{{FROM}}") and n.asExpr() = v)
  or
  "{{FROM}}".toLowerCase().regexpMatch(".*(request|user|input|source|param|remote|body|query|form).*") and
  n instanceof RemoteFlowSource
}

predicate toSpec(DataFlow::Node n) {
  exists(Call c, Name f |
    c.getFunc() = f and f.getId().regexpMatch("{{TO}}") and n.asExpr() = c.getAnArg()
  )
  or
  exists(Call c, Attribute a |
    c.getFunc() = a and a.getName().regexpMatch("{{TO}}") and
    (n.asExpr() = c.getAnArg() or n.asExpr() = a.getObject())
  )
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
