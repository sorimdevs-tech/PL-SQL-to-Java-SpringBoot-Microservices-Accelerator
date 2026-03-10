# Generated from src/parser/generated/PlSql.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .PlSqlParser import PlSqlParser
else:
    from PlSqlParser import PlSqlParser

# This class defines a complete listener for a parse tree produced by PlSqlParser.
class PlSqlListener(ParseTreeListener):

    # Enter a parse tree produced by PlSqlParser#sql_script.
    def enterSql_script(self, ctx:PlSqlParser.Sql_scriptContext):
        pass

    # Exit a parse tree produced by PlSqlParser#sql_script.
    def exitSql_script(self, ctx:PlSqlParser.Sql_scriptContext):
        pass


    # Enter a parse tree produced by PlSqlParser#unit.
    def enterUnit(self, ctx:PlSqlParser.UnitContext):
        pass

    # Exit a parse tree produced by PlSqlParser#unit.
    def exitUnit(self, ctx:PlSqlParser.UnitContext):
        pass


    # Enter a parse tree produced by PlSqlParser#create_procedure_body.
    def enterCreate_procedure_body(self, ctx:PlSqlParser.Create_procedure_bodyContext):
        pass

    # Exit a parse tree produced by PlSqlParser#create_procedure_body.
    def exitCreate_procedure_body(self, ctx:PlSqlParser.Create_procedure_bodyContext):
        pass


    # Enter a parse tree produced by PlSqlParser#create_function_body.
    def enterCreate_function_body(self, ctx:PlSqlParser.Create_function_bodyContext):
        pass

    # Exit a parse tree produced by PlSqlParser#create_function_body.
    def exitCreate_function_body(self, ctx:PlSqlParser.Create_function_bodyContext):
        pass


    # Enter a parse tree produced by PlSqlParser#create_trigger.
    def enterCreate_trigger(self, ctx:PlSqlParser.Create_triggerContext):
        pass

    # Exit a parse tree produced by PlSqlParser#create_trigger.
    def exitCreate_trigger(self, ctx:PlSqlParser.Create_triggerContext):
        pass


    # Enter a parse tree produced by PlSqlParser#create_package.
    def enterCreate_package(self, ctx:PlSqlParser.Create_packageContext):
        pass

    # Exit a parse tree produced by PlSqlParser#create_package.
    def exitCreate_package(self, ctx:PlSqlParser.Create_packageContext):
        pass


    # Enter a parse tree produced by PlSqlParser#anonymous_block.
    def enterAnonymous_block(self, ctx:PlSqlParser.Anonymous_blockContext):
        pass

    # Exit a parse tree produced by PlSqlParser#anonymous_block.
    def exitAnonymous_block(self, ctx:PlSqlParser.Anonymous_blockContext):
        pass


    # Enter a parse tree produced by PlSqlParser#procedure_name.
    def enterProcedure_name(self, ctx:PlSqlParser.Procedure_nameContext):
        pass

    # Exit a parse tree produced by PlSqlParser#procedure_name.
    def exitProcedure_name(self, ctx:PlSqlParser.Procedure_nameContext):
        pass


    # Enter a parse tree produced by PlSqlParser#function_name.
    def enterFunction_name(self, ctx:PlSqlParser.Function_nameContext):
        pass

    # Exit a parse tree produced by PlSqlParser#function_name.
    def exitFunction_name(self, ctx:PlSqlParser.Function_nameContext):
        pass


    # Enter a parse tree produced by PlSqlParser#trigger_name.
    def enterTrigger_name(self, ctx:PlSqlParser.Trigger_nameContext):
        pass

    # Exit a parse tree produced by PlSqlParser#trigger_name.
    def exitTrigger_name(self, ctx:PlSqlParser.Trigger_nameContext):
        pass


    # Enter a parse tree produced by PlSqlParser#package_name.
    def enterPackage_name(self, ctx:PlSqlParser.Package_nameContext):
        pass

    # Exit a parse tree produced by PlSqlParser#package_name.
    def exitPackage_name(self, ctx:PlSqlParser.Package_nameContext):
        pass


    # Enter a parse tree produced by PlSqlParser#table_name.
    def enterTable_name(self, ctx:PlSqlParser.Table_nameContext):
        pass

    # Exit a parse tree produced by PlSqlParser#table_name.
    def exitTable_name(self, ctx:PlSqlParser.Table_nameContext):
        pass


    # Enter a parse tree produced by PlSqlParser#variable_name.
    def enterVariable_name(self, ctx:PlSqlParser.Variable_nameContext):
        pass

    # Exit a parse tree produced by PlSqlParser#variable_name.
    def exitVariable_name(self, ctx:PlSqlParser.Variable_nameContext):
        pass


    # Enter a parse tree produced by PlSqlParser#type_name.
    def enterType_name(self, ctx:PlSqlParser.Type_nameContext):
        pass

    # Exit a parse tree produced by PlSqlParser#type_name.
    def exitType_name(self, ctx:PlSqlParser.Type_nameContext):
        pass


    # Enter a parse tree produced by PlSqlParser#identifier.
    def enterIdentifier(self, ctx:PlSqlParser.IdentifierContext):
        pass

    # Exit a parse tree produced by PlSqlParser#identifier.
    def exitIdentifier(self, ctx:PlSqlParser.IdentifierContext):
        pass


    # Enter a parse tree produced by PlSqlParser#parameter_list.
    def enterParameter_list(self, ctx:PlSqlParser.Parameter_listContext):
        pass

    # Exit a parse tree produced by PlSqlParser#parameter_list.
    def exitParameter_list(self, ctx:PlSqlParser.Parameter_listContext):
        pass


    # Enter a parse tree produced by PlSqlParser#parameter.
    def enterParameter(self, ctx:PlSqlParser.ParameterContext):
        pass

    # Exit a parse tree produced by PlSqlParser#parameter.
    def exitParameter(self, ctx:PlSqlParser.ParameterContext):
        pass


    # Enter a parse tree produced by PlSqlParser#parameter_name.
    def enterParameter_name(self, ctx:PlSqlParser.Parameter_nameContext):
        pass

    # Exit a parse tree produced by PlSqlParser#parameter_name.
    def exitParameter_name(self, ctx:PlSqlParser.Parameter_nameContext):
        pass


    # Enter a parse tree produced by PlSqlParser#parameter_mode.
    def enterParameter_mode(self, ctx:PlSqlParser.Parameter_modeContext):
        pass

    # Exit a parse tree produced by PlSqlParser#parameter_mode.
    def exitParameter_mode(self, ctx:PlSqlParser.Parameter_modeContext):
        pass


    # Enter a parse tree produced by PlSqlParser#datatype.
    def enterDatatype(self, ctx:PlSqlParser.DatatypeContext):
        pass

    # Exit a parse tree produced by PlSqlParser#datatype.
    def exitDatatype(self, ctx:PlSqlParser.DatatypeContext):
        pass


    # Enter a parse tree produced by PlSqlParser#declare_section.
    def enterDeclare_section(self, ctx:PlSqlParser.Declare_sectionContext):
        pass

    # Exit a parse tree produced by PlSqlParser#declare_section.
    def exitDeclare_section(self, ctx:PlSqlParser.Declare_sectionContext):
        pass


    # Enter a parse tree produced by PlSqlParser#variable_declaration.
    def enterVariable_declaration(self, ctx:PlSqlParser.Variable_declarationContext):
        pass

    # Exit a parse tree produced by PlSqlParser#variable_declaration.
    def exitVariable_declaration(self, ctx:PlSqlParser.Variable_declarationContext):
        pass


    # Enter a parse tree produced by PlSqlParser#constant_declaration.
    def enterConstant_declaration(self, ctx:PlSqlParser.Constant_declarationContext):
        pass

    # Exit a parse tree produced by PlSqlParser#constant_declaration.
    def exitConstant_declaration(self, ctx:PlSqlParser.Constant_declarationContext):
        pass


    # Enter a parse tree produced by PlSqlParser#type_declaration.
    def enterType_declaration(self, ctx:PlSqlParser.Type_declarationContext):
        pass

    # Exit a parse tree produced by PlSqlParser#type_declaration.
    def exitType_declaration(self, ctx:PlSqlParser.Type_declarationContext):
        pass


    # Enter a parse tree produced by PlSqlParser#executable_section.
    def enterExecutable_section(self, ctx:PlSqlParser.Executable_sectionContext):
        pass

    # Exit a parse tree produced by PlSqlParser#executable_section.
    def exitExecutable_section(self, ctx:PlSqlParser.Executable_sectionContext):
        pass


    # Enter a parse tree produced by PlSqlParser#statement.
    def enterStatement(self, ctx:PlSqlParser.StatementContext):
        pass

    # Exit a parse tree produced by PlSqlParser#statement.
    def exitStatement(self, ctx:PlSqlParser.StatementContext):
        pass


    # Enter a parse tree produced by PlSqlParser#null_statement.
    def enterNull_statement(self, ctx:PlSqlParser.Null_statementContext):
        pass

    # Exit a parse tree produced by PlSqlParser#null_statement.
    def exitNull_statement(self, ctx:PlSqlParser.Null_statementContext):
        pass


    # Enter a parse tree produced by PlSqlParser#assignment_statement.
    def enterAssignment_statement(self, ctx:PlSqlParser.Assignment_statementContext):
        pass

    # Exit a parse tree produced by PlSqlParser#assignment_statement.
    def exitAssignment_statement(self, ctx:PlSqlParser.Assignment_statementContext):
        pass


    # Enter a parse tree produced by PlSqlParser#if_statement.
    def enterIf_statement(self, ctx:PlSqlParser.If_statementContext):
        pass

    # Exit a parse tree produced by PlSqlParser#if_statement.
    def exitIf_statement(self, ctx:PlSqlParser.If_statementContext):
        pass


    # Enter a parse tree produced by PlSqlParser#loop_statement.
    def enterLoop_statement(self, ctx:PlSqlParser.Loop_statementContext):
        pass

    # Exit a parse tree produced by PlSqlParser#loop_statement.
    def exitLoop_statement(self, ctx:PlSqlParser.Loop_statementContext):
        pass


    # Enter a parse tree produced by PlSqlParser#sql_statement.
    def enterSql_statement(self, ctx:PlSqlParser.Sql_statementContext):
        pass

    # Exit a parse tree produced by PlSqlParser#sql_statement.
    def exitSql_statement(self, ctx:PlSqlParser.Sql_statementContext):
        pass


    # Enter a parse tree produced by PlSqlParser#exception_section.
    def enterException_section(self, ctx:PlSqlParser.Exception_sectionContext):
        pass

    # Exit a parse tree produced by PlSqlParser#exception_section.
    def exitException_section(self, ctx:PlSqlParser.Exception_sectionContext):
        pass


    # Enter a parse tree produced by PlSqlParser#exception_handler.
    def enterException_handler(self, ctx:PlSqlParser.Exception_handlerContext):
        pass

    # Exit a parse tree produced by PlSqlParser#exception_handler.
    def exitException_handler(self, ctx:PlSqlParser.Exception_handlerContext):
        pass


    # Enter a parse tree produced by PlSqlParser#exception_name.
    def enterException_name(self, ctx:PlSqlParser.Exception_nameContext):
        pass

    # Exit a parse tree produced by PlSqlParser#exception_name.
    def exitException_name(self, ctx:PlSqlParser.Exception_nameContext):
        pass


    # Enter a parse tree produced by PlSqlParser#condition.
    def enterCondition(self, ctx:PlSqlParser.ConditionContext):
        pass

    # Exit a parse tree produced by PlSqlParser#condition.
    def exitCondition(self, ctx:PlSqlParser.ConditionContext):
        pass


    # Enter a parse tree produced by PlSqlParser#expression.
    def enterExpression(self, ctx:PlSqlParser.ExpressionContext):
        pass

    # Exit a parse tree produced by PlSqlParser#expression.
    def exitExpression(self, ctx:PlSqlParser.ExpressionContext):
        pass


    # Enter a parse tree produced by PlSqlParser#term.
    def enterTerm(self, ctx:PlSqlParser.TermContext):
        pass

    # Exit a parse tree produced by PlSqlParser#term.
    def exitTerm(self, ctx:PlSqlParser.TermContext):
        pass


    # Enter a parse tree produced by PlSqlParser#factor.
    def enterFactor(self, ctx:PlSqlParser.FactorContext):
        pass

    # Exit a parse tree produced by PlSqlParser#factor.
    def exitFactor(self, ctx:PlSqlParser.FactorContext):
        pass


    # Enter a parse tree produced by PlSqlParser#function_call.
    def enterFunction_call(self, ctx:PlSqlParser.Function_callContext):
        pass

    # Exit a parse tree produced by PlSqlParser#function_call.
    def exitFunction_call(self, ctx:PlSqlParser.Function_callContext):
        pass


    # Enter a parse tree produced by PlSqlParser#procedure_call.
    def enterProcedure_call(self, ctx:PlSqlParser.Procedure_callContext):
        pass

    # Exit a parse tree produced by PlSqlParser#procedure_call.
    def exitProcedure_call(self, ctx:PlSqlParser.Procedure_callContext):
        pass


    # Enter a parse tree produced by PlSqlParser#return_statement.
    def enterReturn_statement(self, ctx:PlSqlParser.Return_statementContext):
        pass

    # Exit a parse tree produced by PlSqlParser#return_statement.
    def exitReturn_statement(self, ctx:PlSqlParser.Return_statementContext):
        pass


    # Enter a parse tree produced by PlSqlParser#expression_list.
    def enterExpression_list(self, ctx:PlSqlParser.Expression_listContext):
        pass

    # Exit a parse tree produced by PlSqlParser#expression_list.
    def exitExpression_list(self, ctx:PlSqlParser.Expression_listContext):
        pass



del PlSqlParser