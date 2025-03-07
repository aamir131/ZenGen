from enum import Enum
import copy
import decimal

class ScalarType(Enum):
    K = "k"
    M = "m"
    B = "b"

class Signed(Enum):
    Negative = "-"
    Positive = "+"
    
class PrefixQuantityType(Enum):
    Pound = "£"
    Dollar = "$"
    Euros = "€"

class SuffixQuantityType(Enum):
    Percentage = "%"
    X = "x"
    
QuantityType = PrefixQuantityType | SuffixQuantityType

class ExcelNumber:

    def __init__(self, s: str):
        initial_s = s
        
        # If the string is empty, raise an error
        if len(s) == 0: raise TypeError("Empty String Passed to ExcelNumber Type")
        s = s.lower().replace(" trillion", "000b").replace("bn", "b").replace(",", "").replace("trillion", "000b").replace(" ", "").rstrip('.').replace("million", "m").replace("thousand", "k").replace("billion", "b").replace("mn", "m").replace("bps", "%").replace("~", "").replace("pps", "%")

        # if any(str(year) in s.strip(",.)") for year in range(1900, 2100)):
        #             raise TypeError("Invalid argument passed to ExcelNumber Type - Contains year")

        # stripped_s = s
        # for i in  ",.()kmb-+£$€x%":
        #     stripped_s = stripped_s.replace(i, "")
        # if stripped_s.replace("0", "").replace("1", "") == "":
        #     raise TypeError("Invalid argument passed to ExcelNumber")

        if "(" in s and ")" not in s or "-" in s:
            s = s.replace("(", "")
        
        if ")" in s and "(" not in s or "-" in s:
            s = s.replace(")", "")

        self.quantity_type: QuantityType | None  = None
        self.signed_type: Signed | None = None 
        self.scalar_type: ScalarType | None = None
        self.val: str = ""
        
        # Over here we only take care of the sign
        match s:
            # x is either a percentage, a pure number or a scalar: £12.7, 12.7%, 12.7m, £12.7m, 1.1k%
            case _ if ExcelNumber.is_quantity(s):
                self.initialise_absolute_quantity(s)
            case _ if (s[0] + s[-1] == "()") and ExcelNumber.is_quantity(s[1:-1]):
                # (x)
                self.signed_type = Signed.Negative
                self.initialise_absolute_quantity(s[1:-1])
            case _ if s[0] in Signed and ExcelNumber.is_quantity(s[1:]):
                # +x, -x
                self.signed_type = Signed(s[0])
                self.initialise_absolute_quantity(s[1:])
            case _ if s[0] in PrefixQuantityType and (s[1] + s[-1] == "()") and ExcelNumber.is_quantity(s[0] + s[2:-1]):
                # $(x), $(x), $(xm)
                self.signed_type = Signed.Negative
                self.initialise_absolute_quantity(s[0] + s[2:-1])
            case _ if s[-1] in SuffixQuantityType and (s[1] + s[-2] == "()") and ExcelNumber.is_quantity(s[0] + s[2:-2]):
                # (x)%, (x)x
                self.signed_type = Signed.Negative
                self.initialise_absolute_quantity(s[0] + s[2:-1])
            case _ if s[0] in PrefixQuantityType and (s[1] + s[-2] == "()") and ExcelNumber.is_quantity(s[0] + s[2:-2] + s[-1]) :
                # $(x)k, £(x)m
                self.signed_type = Signed.Negative
                self.initialise_absolute_quantity(s[0] + s[2:-2] + s[-1])
            case _ if s[-1] in SuffixQuantityType and (s[0] + s[-2] == "()") and ExcelNumber.is_quantity(s[1:-2] + s[-1]) :
                # (x)x, (x)m
                self.signed_type = Signed.Negative
                self.initialise_absolute_quantity(s[1:-2] + s[-1])
            case _:
                raise TypeError("Did not match any case")
            
        if "bps" in initial_s or "pps" in initial_s:
            self.val = ExcelNumber.divide_by_exp(self.val, 2)


    def initialise_absolute_quantity(self, s: str):
        if s[0] in PrefixQuantityType:
            self.quantity_type = PrefixQuantityType(s[0])
            s = s[1:]
        elif s[-1]in SuffixQuantityType: 
            self.quantity_type = SuffixQuantityType(s[-1])
            s = s[:-1]
        
        if s[-1] in ScalarType:
            self.scalar_type = ScalarType(s[-1])
            s = s[:-1]
        if not ExcelNumber.is_pure_number(s): raise TypeError("Should be of type number")
        try:
            float(s)
        except:
            raise TypeError("Invalid argument. Should be a number")
        self.val = s

    @staticmethod
    def is_excel_number(text):
        try:
            return ExcelNumber(text)
        except:
            return False
    
    @staticmethod
    def is_pure_number(s: str): return s.replace('.', '', 1).isdigit()
    
    @staticmethod
    def is_num_with_suffix(s: str): return ExcelNumber.is_pure_number(s[:-1]) and s[-1] in ScalarType
    
    @staticmethod
    def is_num_with_suffix_or_pure_number(s):
        return s.replace('.', '', 1).isdigit() or ExcelNumber.is_num_with_suffix(s)
    
    @staticmethod
    def is_prefix_quantity(s: str):
        return s[0] in PrefixQuantityType and ExcelNumber.is_num_with_suffix_or_pure_number(s[1:])
    
    @staticmethod
    def is_suffix_quantity(s: str):
        return s[-1] in SuffixQuantityType and ExcelNumber.is_num_with_suffix_or_pure_number(s[:-1])
    
    @staticmethod
    def is_quantity(s: str):
        return ExcelNumber.is_prefix_quantity(s) or ExcelNumber.is_suffix_quantity(s) or ExcelNumber.is_num_with_suffix_or_pure_number(s)
    
    @staticmethod
    def tree_equal_str(a: str, b: str):
        if a == b: return True
        if "." not in a + b: return False
        if "." in a and (len(a) - a.find(".") >= len(b) - b.find(".") or "." not in b):
            numbers_after_dot = len(a) - a.find(".") - 1
            tree = ([f'%.{i}f' % round(float(a)+0.0000000000001, i) for i in range(numbers_after_dot, 0, -1)] + [str(int(round(float(a)+0.000000000001, 0)))])
            return b in tree
        return ExcelNumber.tree_equal_str(b, a)
        
    def percentage_equal(self, other):
        if {self.quantity_type, other.quantity_type} == {SuffixQuantityType.Percentage}:
            return ExcelNumber.tree_equal_str(self.val, other.val)
        
        b, a = (self.val, other.val) if self.quantity_type == SuffixQuantityType.Percentage else (other.val, self.val)
        return any(ExcelNumber.tree_equal_str(a, x) for x in [b, ExcelNumber.divide_by_exp(b, 2)])
        
    @staticmethod
    def divide_by_exp(val: str, exp: int) -> str:
        if "-" in val:
            return "-" + ExcelNumber.divide_by_exp(val.replace("-", ""), exp)
        if exp < 0: 
            raise ValueError("Can't divide by a negative exponent")
        if exp == 0: return val
        if not "." in val:
            if exp < len(val):
                return val[:-exp] + "." +val[-exp:]
            return "0." + "0" * (exp - len(val)) + val
        return ExcelNumber.divide_by_exp(val.replace(".", ""), exp + len(val) - val.find(".") - 1)
    
    @staticmethod
    def multiply_by_exp(val: str, exp: int) -> str:
        if val[0] == "-":
            return "-"+ ExcelNumber.multiply_by_exp(val[1:], exp)
        if not "." in val:
            return val + "0" * exp
        k = val.index(".") + exp
        val = val.replace(".", "")
        if k >= len(val):
            return val + "0" * (k - len(val))
        return val[:k] + "." + val[k:]
    
    @staticmethod
    def get_scale(x: ScalarType):
        return ("kmb".index(x.value) + 1) * 3 if x else 0
        
    def scalars_equal(self, other):
        s = ExcelNumber.divide_by_exp(self.val, 9 - ExcelNumber.get_scale(self.scalar_type) if self.scalar_type else 0)
        o = ExcelNumber.divide_by_exp(other.val, 9 - ExcelNumber.get_scale(other.scalar_type) if other.scalar_type else 0)
        if self.scalar_type and other.scalar_type: return ExcelNumber.tree_equal_str(s, o)
        if not self.scalar_type and not other.scalar_type:
            k1 = [ExcelNumber.divide_by_exp(self.val, 3 * i) for i in range(0, 4)]
            k2 = [ExcelNumber.divide_by_exp(other.val, 3 * i) for i in range(0, 4)]
            return any(ExcelNumber.tree_equal_str(i, j) for i in k1 for j in k2)
        if not self.scalar_type:
            return any(ExcelNumber.tree_equal_str(o, ExcelNumber.divide_by_exp(self.val, 3*i)) for i in range(4))
        return other == self

    def __eq__(self, other) -> bool:

        if len({self.quantity_type, other.quantity_type} - {None}) > 1:
            return False
        if len({self.signed_type, other.signed_type} - {None}) > 1:
            return False
        
        if {SuffixQuantityType.Percentage} <= {self.quantity_type, other.quantity_type}:
            return self.percentage_equal(other)
        return self.scalars_equal(other)
        
    def __str__(self):
        s = self.val + self.scalar_type.value if self.scalar_type else self.val
        s = self.quantity_type.value + s if self.quantity_type in PrefixQuantityType else s
        s = s + self.quantity_type.value if self.quantity_type in SuffixQuantityType else s
        s = "-" + s if self.signed_type == Signed.Negative else s
        return s

    def __repr__(self):
        return str(self)
    
    def get_properties_stringified(self) -> tuple[str, str, str, str]:
        return (self.quantity_type.value if self.quantity_type else "", self.signed_type.value if self.signed_type else "", self.scalar_type.value if self.scalar_type else "", self.val)
    
    def __abs__(self):
        return ExcelNumber(str(abs(float(self.val))))
    
    def __add__(self, other):

        if isinstance(other, (str, int, float)):
            return self + ExcelNumber(str(other))
        
        if len({self.quantity_type, other.quantity_type, None}) > 2:
            raise ValueError("Numbers do not conform for addition")
        
        if self.quantity_type == None and other.quantity_type != None:
            return other + self

        if self.quantity_type == SuffixQuantityType.Percentage and other.quantity_type == None:
            v1 = decimal.Decimal(self.val) * (-1 if self.signed_type == Signed.Negative else 1)
            v2 = decimal.Decimal(ExcelNumber.multiply_by_exp(other.val, 2)) * (-1 if other.signed_type == Signed.Negative else 1)
            return ExcelNumber(str(v1 + v2) + "%")

        if self.quantity_type == SuffixQuantityType.Percentage and other.quantity_type == SuffixQuantityType.Percentage:
            v1 = decimal.Decimal(self.val) * (-1 if self.signed_type == Signed.Negative else 1)
            v2 = decimal.Decimal(other.val) * (-1 if other.signed_type == Signed.Negative else 1)
            return ExcelNumber(str(v1 + v2) + "%")
        
        new_quantity_type = self.quantity_type or other.quantity_type

        val1 = (int(self.val) if "." not in self.val else float(self.val)) * (-1 if self.signed_type == Signed.Negative else 1)
        val1 = val1 * 10 ** (ExcelNumber.get_scale(self.scalar_type) if self.scalar_type else 0)

        val2 = (int(other.val) if "." not in other.val else float(other.val)) * (-1 if other.signed_type == Signed.Negative else 1)
        val2 = val2 * 10 ** (ExcelNumber.get_scale(other.scalar_type) if other.scalar_type else 0)
        s = val1 + val2
        h = ("-" if "-" in str(s) else "") + (new_quantity_type.value if new_quantity_type in PrefixQuantityType else "") + (str(s)[1:] if "-" in str(s) else str(s)) + (new_quantity_type.value if new_quantity_type in SuffixQuantityType else "")
        return ExcelNumber(h)
    
    def __truediv__(self, other):
        
        if isinstance(other, (str, int, float)):
            return self / ExcelNumber(str(other))
        
        if self.quantity_type == None and other.quantity_type == SuffixQuantityType.Percentage:
            return other / self

        if self.quantity_type == SuffixQuantityType.Percentage and other.quantity_type == SuffixQuantityType.Percentage:
            return ExcelNumber(ExcelNumber.divide_by_exp(str((decimal.Decimal(self.val) / decimal.Decimal(other.val)) * (1 if self.signed_type == other.signed_type else -1)), 2) + "%")
        
        if self.quantity_type == SuffixQuantityType.Percentage and other.quantity_type == None:
            return ExcelNumber(str((decimal.Decimal(self.val) / decimal.Decimal(other.val)) * (1 if self.signed_type == other.signed_type else -1)) + "%")
        
        if self.quantity_type == SuffixQuantityType.Percentage and other.quantity_type != None and other.quantity_type != SuffixQuantityType.Percentage:
            return other / self
        
        if other.quantity_type == SuffixQuantityType.Percentage and self.quantity_type != None and self.quantity_type != SuffixQuantityType.Percentage:
            return self / ExcelNumber(ExcelNumber.divide_by_exp(("-" if other.signed_type == Signed.Negative else "") + other.val, 2))
        
        if self.quantity_type == other.quantity_type:
            k1 = copy.deepcopy(self)
            k1.val = str(decimal.Decimal(k1.val) / decimal.Decimal(other.val))
            k1.quantity_type = None
            return k1
        
        #if self.quantity_type != None and other.quantity_type != None:
        #    raise ValueError("Numbers do not conform for multiplication")
        
        if self.quantity_type != None and other.quantity_type != None:
            raise ValueError("Can't multiply quantities with different prefixes")
        
        val1 = (int(self.val) if "." not in self.val else float(self.val))
        val2 = (int(other.val) if "." not in other.val else float(other.val))
        s = decimal.Decimal(str(val1)) / decimal.Decimal(str(val2)) * (1 if self.signed_type == other.signed_type else -1)
        res = ExcelNumber(str(s))

        new_quantity_type = {self.quantity_type, other.quantity_type} - {None}
        if len(new_quantity_type) > 1:
            raise ValueError("Can't add quantities with different prefixes")
        new_quantity_type = new_quantity_type.pop() if new_quantity_type else None
        res.quantity_type = new_quantity_type

        res.signed_type = Signed.Positive if self.signed_type == other.signed_type else Signed.Negative

        new_scale = self.get_scale(self.scalar_type) - self.get_scale(other.scalar_type)
        if new_scale < 0:
            res.val = ExcelNumber.divide_by_exp(res.val, -new_scale)
            new_scale = 0
        res.scalar_type = ScalarType(" kmb"[new_scale // 3]) if new_scale != 0 else None
        return res

    def __mul__(self, other):
        
        if isinstance(other, (str, int, float)):
            return self * ExcelNumber(str(other))
        
        if len({self.quantity_type, other.quantity_type, SuffixQuantityType.Percentage, None}) > 3:
            raise ValueError("Numbers do not conform for multiplication")
        
        if self.quantity_type == None and other.quantity_type != None:
            return other * self

        if self.quantity_type == SuffixQuantityType.Percentage and other.quantity_type == SuffixQuantityType.Percentage:
            return ExcelNumber(ExcelNumber.divide_by_exp(str(decimal.Decimal(self.val) * decimal.Decimal(other.val) * (1 if self.signed_type == other.signed_type else -1)), 2) + "%")
        
        if self.quantity_type == SuffixQuantityType.Percentage:
            val = str(decimal.Decimal(self.val) * decimal.Decimal(other.val) * (1 if self.signed_type == other.signed_type else -1))
            val = ExcelNumber.divide_by_exp(val, 2)
            h = ExcelNumber(val)
            h.quantity_type = other.quantity_type
            return h
        
        if self.quantity_type == SuffixQuantityType.Percentage and other.quantity_type != None and other.quantity_type != SuffixQuantityType.Percentage:
            return other * self
        
        if other.quantity_type == SuffixQuantityType.Percentage and self.quantity_type != None and self.quantity_type != SuffixQuantityType.Percentage:
            return self * ExcelNumber(ExcelNumber.divide_by_exp(("-" if other.signed_type == Signed.Negative else "") + other.val, 2))
        
        val1 = (int(self.val) if "." not in self.val else float(self.val))
        val2 = (int(other.val) if "." not in other.val else float(other.val))
        s = decimal.Decimal(str(val1)) * decimal.Decimal(str(val2)) * (1 if self.signed_type == other.signed_type else -1)
        res = ExcelNumber(str(s))

        new_quantity_type = {self.quantity_type, other.quantity_type} - {None}
        new_quantity_type = new_quantity_type.pop() if new_quantity_type else None
        res.quantity_type = new_quantity_type

        res.signed_type = Signed.Positive if self.signed_type == other.signed_type else Signed.Negative

        new_scale = self.get_scale(self.scalar_type) + self.get_scale(other.scalar_type)
        if new_scale > 9:
            res.val = ExcelNumber.multiply_by_exp(res.val, new_scale - 9)
            new_scale = 9
        res.scalar_type = ScalarType(" kmb"[new_scale // 3]) if new_scale != 0 else None
        return res

    def __sub__(self, other):
        if isinstance(other, (str, int, float)):
            return self + (-ExcelNumber(str(other)))
        return self + (-other)

    def __neg__(self):
        new_excel_number = copy.deepcopy(self)
        new_excel_number.signed_type = Signed.Negative if self.signed_type != Signed.Negative else None
        return new_excel_number
        
    def __pow__(self, other):

        if isinstance(other, (str, int, float)):
            return self ** ExcelNumber(str(other))
        
        if other.quantity_type is not None:
            raise ValueError("Exponent cannot have a quantity type")
        
        if other.signed_type == Signed.Negative:
            raise ValueError("Exponent cannot be negative")

        if self.quantity_type == SuffixQuantityType.Percentage:
            k1 = copy.deepcopy(self)
            k1.val = ExcelNumber.divide_by_exp(k1.val, 2)
            k1.val = str(decimal.Decimal(k1.val) ** decimal.Decimal(other.val))
            k1.val = ExcelNumber.multiply_by_exp(k1.val, 2)
            return k1

        val1 = (int(self.val) if "." not in self.val else float(self.val)) * (-1 if self.signed_type == Signed.Negative else 1)
        val1 = val1 * 10 ** (ExcelNumber.get_scale(self.scalar_type) if self.scalar_type else 0)

        val2 = (int(other.val) if "." not in other.val else float(other.val)) * (-1 if other.signed_type == Signed.Negative else 1)
        
        s = decimal.Decimal(str(val1)) ** decimal.Decimal(str(val2))
        h = ("-" if "-" in str(s) else "") + (self.quantity_type.value if self.quantity_type in PrefixQuantityType else "") + (str(s)[1:] if "-" in str(s) else str(s)) + (self.quantity_type.value if self.quantity_type in SuffixQuantityType else "")
        return ExcelNumber(h)
    
    
    def __rsub__(self, other):
        if isinstance(other, (str, int, float)):
            return ExcelNumber(str(other)) - self
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, (str, int, float)):
            return ExcelNumber(str(other)) + self
        return NotImplemented

    def __rmul__(self, other):
        if isinstance(other, (str, int, float)):
            return ExcelNumber(str(other)) * self
        return NotImplemented

    def __rtruediv__(self, other):
        if isinstance(other, (str, int, float)):
            return ExcelNumber(str(other)) / self
        return NotImplemented
