/**
 * @name FastAPI Function to Router Definition Mapping
 * @description Map decorated functions to their router definitions
 * @kind problem
 * @problem.severity info
 * @id fastapi-function-to-router
 */
import python
import semmle.python.pointsto.PointsTo

from FunctionExpr func, Call decorator, Attribute attr, Name router_var, AssignStmt router_def, Call constructor, Name constructor_name
where
  // Function with FastAPI decorator
  decorator = func.getADecorator() and
  decorator.getFunc() = attr and
  attr.getObject() = router_var and
  attr.getName() in ["get", "post", "put", "delete", "patch", "head", "options"] and
  
  // Router definition
  router_def.getValue() = constructor and
  constructor.getFunc() = constructor_name and
  constructor_name.getId() in ["FastAPI", "APIRouter"] and
  
  // Connect usage to definition via points-to
  exists(ControlFlowNode origin |
    PointsTo::pointsTo(router_var.getAFlowNode(), _, _, origin) and
    origin.getNode() = constructor
  ) and
  
  // Filter application code only
  not func.getLocation().getFile().getRelativePath().matches("%/site-packages/%") and
  not func.getLocation().getFile().getRelativePath().matches("%/lib/python%") and
  not func.getLocation().getFile().getRelativePath().matches("%/__pycache__/%") and
  not func.getLocation().getFile().getRelativePath().matches("%/venv/%") and
  not func.getLocation().getFile().getRelativePath().matches("%/virtualenv/%") and
  
  // Ensure valid locations
  exists(func.getLocation().getFile()) and
  exists(router_def.getLocation().getFile()) and
  func.getLocation().getFile().getRelativePath().matches("%.py")

select func,
       func.getName() + "@" +
       func.getLocation().getFile().getRelativePath() + ":" +
       func.getLocation().getStartLine().toString() +
       " -> " +
    //    router_var.getId() + "@" +
       router_def.getLocation().getFile().getRelativePath() + ":" +
       router_def.getLocation().getStartLine().toString() + ":" +
       router_def.getLocation().getEndLine().toString()