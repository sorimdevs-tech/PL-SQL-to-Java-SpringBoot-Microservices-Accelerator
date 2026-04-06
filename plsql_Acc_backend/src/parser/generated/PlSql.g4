grammar PlSql;

sql_script
    : unit* EOF
    ;

unit
    : create_procedure_body
    | create_function_body
    | create_trigger
    | create_package
    | anonymous_block
    | sql_statement
    ;

create_procedure_body
    : CREATE (OR REPLACE)? PROCEDURE procedure_name parameter_list?
      (IS | AS)
      declare_section?
      BEGIN executable_section
      (EXCEPTION exception_section)?
      END procedure_name?
      SEMI?
      DIV?
    ;

create_function_body
    : CREATE (OR REPLACE)? FUNCTION function_name parameter_list?
      RETURN datatype
      (IS | AS)
      declare_section?
      BEGIN executable_section
      (EXCEPTION exception_section)?
      END function_name?
      SEMI?
      DIV?
    ;

create_trigger
    : CREATE (OR REPLACE)? TRIGGER trigger_name
      (BEFORE | AFTER) (INSERT | UPDATE | DELETE) ON table_name
      (FOR EACH ROW)?
      (IS | AS)
      BEGIN executable_section
      END
      SEMI?
      DIV?
    ;

create_package
    : CREATE (OR REPLACE)? PACKAGE package_name
      (IS | AS)
      .*?
      END package_name?
      SEMI?
      DIV?
    ;

anonymous_block
    : (DECLARE declare_section)?
      BEGIN executable_section
      (EXCEPTION exception_section)?
      END
      SEMI?
      DIV?
    ;

procedure_name : identifier ;
function_name  : identifier ;
trigger_name   : identifier ;
package_name   : identifier ;
table_name     : identifier ;
variable_name  : identifier ;
type_name      : identifier ;

identifier
    : ID
    | QUOTED_ID
    ;

parameter_list
    : LPAREN parameter (COMMA parameter)* RPAREN
    ;

parameter
    : parameter_name datatype parameter_mode?
    ;

parameter_name : identifier ;
parameter_mode : IN | OUT | IN OUT ;

datatype
    : identifier (LPAREN NUMBER_LITERAL (COMMA NUMBER_LITERAL)? RPAREN)?
    | VARCHAR2
    | NUMBER
    | DATE
    | BOOLEAN
    ;

declare_section
    : (variable_declaration | constant_declaration | type_declaration)*
    ;

variable_declaration
    : variable_name datatype (ASSIGN expression)? SEMI?
    ;

constant_declaration
    : variable_name CONSTANT datatype ASSIGN expression SEMI?
    ;

type_declaration
    : TYPE type_name IS datatype SEMI?
    ;

executable_section
    : statement*
    ;

statement
    : assignment_statement
    | procedure_call
    | return_statement
    | null_statement
    | if_statement
    | loop_statement
    | sql_statement
    ;

null_statement
    : NULL_ SEMI?
    ;

assignment_statement
    : variable_name ASSIGN expression SEMI?
    ;

if_statement
    : IF condition THEN executable_section
      (ELSIF condition THEN executable_section)*
      (ELSE executable_section)?
      END IF
      SEMI?
    ;

loop_statement
    : LOOP executable_section END LOOP SEMI?
    | WHILE condition LOOP executable_section END LOOP SEMI?
    | FOR identifier IN NUMBER_LITERAL RANGE_DOTS NUMBER_LITERAL LOOP executable_section END LOOP SEMI?
    ;

sql_statement
    : (SELECT | INSERT | UPDATE | DELETE | MERGE) .*? SEMI
    ;

exception_section
    : exception_handler+
    ;

exception_handler
    : WHEN exception_name THEN executable_section
    ;

exception_name
    : identifier
    | OTHERS
    ;

condition
    : expression (EQ | NEQ | LT | LTE | GT | GTE) expression
    | expression
    ;

expression
    : term ((PLUS | MINUS) term)*
    ;

term
    : factor ((STAR | DIV) factor)*
    ;

factor
    : NUMBER_LITERAL
    | STRING_LITERAL
    | variable_name
    | function_call
    | LPAREN expression RPAREN
    ;

function_call
    : function_name LPAREN expression_list? RPAREN
    ;

procedure_call
    : procedure_name LPAREN expression_list? RPAREN SEMI?
    ;

return_statement
    : RETURN expression? SEMI?
    ;

expression_list
    : expression (COMMA expression)*
    ;

CREATE   : 'CREATE';
OR       : 'OR';
REPLACE  : 'REPLACE';
PROCEDURE: 'PROCEDURE';
FUNCTION : 'FUNCTION';
TRIGGER  : 'TRIGGER';
PACKAGE  : 'PACKAGE';
IS       : 'IS';
AS       : 'AS';
BEGIN    : 'BEGIN';
END      : 'END';
DECLARE  : 'DECLARE';
EXCEPTION: 'EXCEPTION';
WHEN     : 'WHEN';
THEN     : 'THEN';
ELSE     : 'ELSE';
ELSIF    : 'ELSIF';
IF       : 'IF';
LOOP     : 'LOOP';
FOR      : 'FOR';
WHILE    : 'WHILE';
RETURN   : 'RETURN';
CONSTANT : 'CONSTANT';
TYPE     : 'TYPE';
SELECT   : 'SELECT';
INSERT   : 'INSERT';
UPDATE   : 'UPDATE';
DELETE   : 'DELETE';
MERGE    : 'MERGE';
ON       : 'ON';
IN       : 'IN';
OUT      : 'OUT';
OTHERS   : 'OTHERS';
NULL_    : 'NULL';
BEFORE   : 'BEFORE';
AFTER    : 'AFTER';
EACH     : 'EACH';
ROW      : 'ROW';
VARCHAR2 : 'VARCHAR2';
NUMBER   : 'NUMBER';
DATE     : 'DATE';
BOOLEAN  : 'BOOLEAN';

ASSIGN    : ':=';
RANGE_DOTS: '..';
EQ        : '=';
NEQ       : '!=' | '<>';
LTE       : '<=';
GTE       : '>=';
LT        : '<';
GT        : '>';
PLUS      : '+';
MINUS     : '-';
STAR      : '*';
DIV       : '/';
SEMI      : ';';
COMMA     : ',';
LPAREN    : '(';
RPAREN    : ')';

NUMBER_LITERAL
    : [0-9]+ ('.' [0-9]+)?
    ;

STRING_LITERAL
    : '\'' ('\'\'' | ~'\'')* '\''
    ;

QUOTED_ID
    : '"' (~["])+ '"'
    ;

ID
    : [a-zA-Z_][a-zA-Z0-9_$#]*
    ;

WS
    : [ \t\r\n]+ -> skip
    ;

COMMENT
    : '--' ~[\r\n]* -> skip
    ;

MULTILINE_COMMENT
    : '/*' .*? '*/' -> skip
    ;
