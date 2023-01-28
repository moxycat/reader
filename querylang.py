from rply import LexerGenerator, ParserGenerator
from rply.token import BaseBox
import operator
import re
import traceback

class String(BaseBox):
    def __init__(self, value): self.value = str(value)
    def eval(self, _): return self.value
    def repr(self): return "String(\"%s\")" % self.value

class Number(BaseBox):
    def __init__(self, value): self.value = float(value)
    def eval(self, _): return self.value
    def repr(self): return "Number(%d)" % self.value

class Boolean(BaseBox):
    def __init__(self, value): self.value = bool(value)

class List(BaseBox):
    def __init__(self, head): self.contents = [head]
    def eval(self, rows): return [x.eval(rows) for x in self.contents]
    def repr(self): return "List(%s)" % ", ".join([x.repr() for x in self.contents])
    def append(self, e): self.contents.append(e)

class Variable(BaseBox):
    def __init__(self, name: str): self.name = str(name)
    def eval(self, _): return self.name
    def repr(self): return "Variable(%s)" % self.name

class Not(BaseBox):
    def __init__(self, value): self.value = value
    def repr(self): return "Not(%s)" % self.value.repr()
    def eval(self, rows):
        return [x for x in rows if x not in self.value.eval(rows)]

class BinaryOp(BaseBox):
    def __init__(self, left, right):
        self.left = left
        self.right = right
    def filter(self, key, value, rows, op):
        result = []
        for row in rows:
            if (x := row.get(key)) is not None and (op(x, value) == True): result.append(row)
        return result

class LT(BinaryOp):
    def repr(self): return "LessThan(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        return self.filter(self.left.eval(rows), self.right.eval(rows), rows, operator.lt)

class GT(BinaryOp):
    def repr(self): return "GreaterThan(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        return self.filter(self.left.eval(rows), self.right.eval(rows), rows, operator.gt)

class LTE(BinaryOp):
    def repr(self): return "LessThanOrEqual(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        return self.filter(self.left.eval(rows), self.right.eval(rows), rows, operator.le)

class GTE(BinaryOp):
    def repr(self): return "GreaterThanOrEqual(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        return self.filter(self.left.eval(rows), self.right.eval(rows), rows, operator.ge)

class EQ(BinaryOp):
    def repr(self): return "Equal(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        return self.filter(self.left.eval(rows), self.right.eval(rows), rows, operator.eq)

class NEQ(BinaryOp):
    def repr(self): return "NotEqual(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        return self.filter(self.left.eval(rows), self.right.eval(rows), rows, operator.ne)

class Match(BinaryOp):
    def repr(self): return "Match(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        result = []
        pattern = self.right.eval(rows)
        key = self.left.eval(rows)
        for row in rows:
            if (val := row.get(key)) is not None:
                m = re.match(pattern, val, re.IGNORECASE)
                if m is None: continue
                result.append(row)
        return result

class Member(BinaryOp):
    def repr(self): return "Member(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        result = []
        key = self.left.eval(rows)
        possible = self.right.eval(rows)

        for row in rows:
            if (x := row.get(key)) is not None and x in possible: result.append(row)

        return result

class MemberReverse(BinaryOp): # again, really lazy but idc
    def repr(self): return "MemberReverse(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        result = []
        key = self.left.eval(rows)
        val = self.right.eval(rows)

        for row in rows:
            if (x := row.get(key)) is not None and val in x: result.append(row)

        return result

class Subset(BinaryOp):
    def repr(self): return "Subset(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        result = []
        var = self.left.eval(rows)
        val = self.right.eval(rows)
        for row in rows:
            if (x := row.get(var)) is not None and all(a in val for a in x): result.append(row)
        return result

class SubsetReverse(BinaryOp):
    def repr(self): return "Subset(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        result = []
        var = self.left.eval(rows)
        val = self.right.eval(rows)
        for row in rows:
            if (x := row.get(var)) is not None and all(a in x for a in val): result.append(row)
        return result

class Any(BinaryOp):
    def repr(self): return "Any(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        result = []
        var = self.left.eval(rows)
        val = self.right.eval(rows)
        for row in rows:
            if (x := row.get(var)) is not None and any(a in val for a in x): result.append(row)
        return result

class AnyReverse(BinaryOp):
    def repr(self): return "Any(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        result = []
        var = self.left.eval(rows)
        val = self.right.eval(rows)
        for row in rows:
            if (x := row.get(var)) is not None and any(a in x for a in val): result.append(row)
        return result

class And(BinaryOp):
    def repr(self): return "And(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        a = self.left.eval(rows)
        b = self.right.eval(rows)
        return [x for x in b if x in a]

class Or(BinaryOp):
    def repr(self): return "Or(%s, %s)" % (self.left.repr(), self.right.repr())
    def eval(self, rows):
        a = self.left.eval(rows)
        b = self.right.eval(rows)
        return a + [x for x in b if x not in a]

class Exists(BaseBox):
    def __init__(self, value):
        self.value = value
    def repr(self): return "Exists(%s)" % self.value.repr()
    def eval(self, rows):
        result = []
        for row in rows:
            if row.get(self.value.eval(rows)) is not None: result.append(row)
        return result

def normalize_string(s: str):
    def replacer(m):
        return m.group()[1:]
    x = s.removeprefix("\"").removesuffix("\"")
    x = re.sub(r"\\.", replacer, x)
    return x

lg = LexerGenerator()
# data
lg.add("ID", r"[A-Za-z_][A-Za-z0-9_]*")
lg.add("STRING", r"\"((?:\\.|[^\\\"])*)\"")
lg.add("NUMBER", r"[-+]?\d*\.?\d+")

# grouping
lg.add("(", r"\(")
lg.add(")", r"\)")
lg.add("[", r"\[")
lg.add("]", r"\]")
lg.add(",", r"\,")

# expressions
lg.add("<=", r"\<\=") # lte
lg.add(">=", r"\>\=") # gte
lg.add(">", r"\>") # gt
lg.add("<", r"\<") # lt
lg.add("=", r"\=") # eq
lg.add("/=", r"\/\=") # neq
lg.add("~", r"\~") # match
lg.add("@", r"\@") # member
lg.add(":", r"\:") # subset
lg.add("?", r"\?")

# logical operators
lg.add("AND", r"\&")
lg.add("OR", r"\|")
lg.add("NOT", r"\!")

lg.ignore("\s+")


pg = ParserGenerator(
    ["ID", "STRING", "NUMBER", "(", ")", "[", "]", ",", "<=", ">=", ">", "<", "=", "/=", "~", ":", "@", "?", "AND", "OR", "NOT"],
    [
        ("left", ["AND", "OR"]),
        ("left", ["<=", ">=", ">", "<", "=", "/=", "~", ":", "@", "?"])
    ]
)
@pg.production("expression : value")
def expression_exists(p):
    return Exists(p[0])

@pg.production("expression : comparator")
def expression_single(p):
    return p[0]

@pg.production("expression : expression AND expression")
@pg.production("expression : expression OR expression")
def expression_binop(p):
    left = p[0]
    right = p[2]
    op = p[1]
    match op.gettokentype():
        case "AND": return And(left, right)
        case "OR": return Or(left, right)

@pg.production("expression : NOT expression")
@pg.production("comparator : NOT comparator")
def negate(p):
    return Not(p[1])

@pg.production("var : ( var )")
@pg.production("value : ( value )")
@pg.production("comparator : ( comparator )")
@pg.production("expression : ( expression )")
def grouping(p):
    return p[1]

@pg.production("comparator : value <= var")
@pg.production("comparator : value >= var")
@pg.production("comparator : value < var")
@pg.production("comparator : value > var")
@pg.production("comparator : value = var")
@pg.production("comparator : value /= var")
@pg.production("comparator : value ~ var")
@pg.production("comparator : value @ var")
@pg.production("comparator : value : var")
@pg.production("comparator : value ? var")
def expression_binop_right(p): # lazy af implementation but idc LOL
    var = p[2]
    val = p[0]
    op = p[1]
    match op.gettokentype():
        case "<=": return GTE(var, val)
        case ">=": return LTE(var, val)
        case "<": return GT(var, val)
        case ">": return LT(var, val)
        case "=": return EQ(var, val)
        case "/=": return NEQ(var, val)
        case "~": return Match(var, val)
        case "@": return MemberReverse(var, val)
        case ":": return SubsetReverse(var, val)
        case "?": return AnyReverse(var, val)

@pg.production("comparator : var <= value")
@pg.production("comparator : var >= value")
@pg.production("comparator : var < value")
@pg.production("comparator : var > value")
@pg.production("comparator : var = value")
@pg.production("comparator : var /= value")
@pg.production("comparator : var ~ value")
@pg.production("comparator : var @ value")
@pg.production("comparator : var : value")
@pg.production("comparator : var ? value")
def expression_binop_left(p):
    var = p[0]
    val = p[2]
    op = p[1]
    match op.gettokentype():
        case "<=": return LTE(var, val)
        case ">=": return GTE(var, val)
        case "<": return LT(var, val)
        case ">": return GT(var, val)
        case "=": return EQ(var, val)
        case "/=": return NEQ(var, val)
        case "~": return Match(var, val)
        case "@": return Member(var, val)
        case ":": return Subset(var, val)
        case "?": return Any(var, val)

@pg.production("list : [ list_inner ]")
def valuelist(p):
    return p[1]

@pg.production("value : list")
def value_is_list(p):
    return p[0]

@pg.production("list_inner : value")
def list_single(p):
    return List(p[0])

@pg.production("list_inner : list_inner , value")
def list_append(p):
    p[0].append(p[2])
    return p[0]

@pg.production("var : ID")
@pg.production("value : STRING")
@pg.production("value : NUMBER")
def value(p):
    match p[0].gettokentype():
        case "ID": return Variable(p[0].getstr())
        case "STRING": return String(normalize_string(p[0].getstr()))
        case "NUMBER": return Number(p[0].getstr())

lexer = lg.build()
parser = pg.build()

def search(expression, rows, invert=False):
    try:
        obj = parser.parse(lexer.lex(expression), state=None)
        print(obj.repr())
        result = obj.eval(rows)
    except Exception as e:
        print(traceback.format_exc())
        result = []
    if invert:
        return [x for x in rows if x not in result]
    else:
        return result