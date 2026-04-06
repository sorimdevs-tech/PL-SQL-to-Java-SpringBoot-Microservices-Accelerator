# Generated from src/parser/generated/PlSql.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .PlSqlParser import PlSqlParser
else:
    from PlSqlParser import PlSqlParser

# This class defines a complete generic visitor for a parse tree produced by PlSqlParser.

class PlSqlVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by PlSqlParser#sql_script.
    def visitSql_script(self, ctx:PlSqlParser.Sql_scriptContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#unit.
    def visitUnit(self, ctx:PlSqlParser.UnitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#create_procedure_body.
    def visitCreate_procedure_body(self, ctx:PlSqlParser.Create_procedure_bodyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#create_function_body.
    def visitCreate_function_body(self, ctx:PlSqlParser.Create_function_bodyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#create_trigger.
    def visitCreate_trigger(self, ctx:PlSqlParser.Create_triggerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#create_package.
    def visitCreate_package(self, ctx:PlSqlParser.Create_packageContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#anonymous_block.
    def visitAnonymous_block(self, ctx:PlSqlParser.Anonymous_blockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#procedure_name.
    def visitProcedure_name(self, ctx:PlSqlParser.Procedure_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#function_name.
    def visitFunction_name(self, ctx:PlSqlParser.Function_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#trigger_name.
    def visitTrigger_name(self, ctx:PlSqlParser.Trigger_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#package_name.
    def visitPackage_name(self, ctx:PlSqlParser.Package_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#table_name.
    def visitTable_name(self, ctx:PlSqlParser.Table_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#variable_name.
    def visitVariable_name(self, ctx:PlSqlParser.Variable_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#type_name.
    def visitType_name(self, ctx:PlSqlParser.Type_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#identifier.
    def visitIdentifier(self, ctx:PlSqlParser.IdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#parameter_list.
    def visitParameter_list(self, ctx:PlSqlParser.Parameter_listContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#parameter.
    def visitParameter(self, ctx:PlSqlParser.ParameterContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#parameter_name.
    def visitParameter_name(self, ctx:PlSqlParser.Parameter_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#parameter_mode.
    def visitParameter_mode(self, ctx:PlSqlParser.Parameter_modeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#datatype.
    def visitDatatype(self, ctx:PlSqlParser.DatatypeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#declare_section.
    def visitDeclare_section(self, ctx:PlSqlParser.Declare_sectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#variable_declaration.
    def visitVariable_declaration(self, ctx:PlSqlParser.Variable_declarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#constant_declaration.
    def visitConstant_declaration(self, ctx:PlSqlParser.Constant_declarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#type_declaration.
    def visitType_declaration(self, ctx:PlSqlParser.Type_declarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#executable_section.
    def visitExecutable_section(self, ctx:PlSqlParser.Executable_sectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#statement.
    def visitStatement(self, ctx:PlSqlParser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#null_statement.
    def visitNull_statement(self, ctx:PlSqlParser.Null_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#assignment_statement.
    def visitAssignment_statement(self, ctx:PlSqlParser.Assignment_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#if_statement.
    def visitIf_statement(self, ctx:PlSqlParser.If_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#loop_statement.
    def visitLoop_statement(self, ctx:PlSqlParser.Loop_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#sql_statement.
    def visitSql_statement(self, ctx:PlSqlParser.Sql_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#exception_section.
    def visitException_section(self, ctx:PlSqlParser.Exception_sectionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#exception_handler.
    def visitException_handler(self, ctx:PlSqlParser.Exception_handlerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#exception_name.
    def visitException_name(self, ctx:PlSqlParser.Exception_nameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#condition.
    def visitCondition(self, ctx:PlSqlParser.ConditionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#expression.
    def visitExpression(self, ctx:PlSqlParser.ExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#term.
    def visitTerm(self, ctx:PlSqlParser.TermContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#factor.
    def visitFactor(self, ctx:PlSqlParser.FactorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#function_call.
    def visitFunction_call(self, ctx:PlSqlParser.Function_callContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#procedure_call.
    def visitProcedure_call(self, ctx:PlSqlParser.Procedure_callContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#return_statement.
    def visitReturn_statement(self, ctx:PlSqlParser.Return_statementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by PlSqlParser#expression_list.
    def visitExpression_list(self, ctx:PlSqlParser.Expression_listContext):
        return self.visitChildren(ctx)



del PlSqlParser