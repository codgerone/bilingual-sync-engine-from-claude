from defusedxml import minidom

xml_string = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p>
            <w:r><w:t>测试</w:t></w:r>
        </w:p>
    </w:body>
</w:document>
"""

dom = minidom.parseString(xml_string)
t_element = dom.getElementsByTagName('w:t')[0]

print("=" * 70)
print("核心问题：Method 是不是 Attribute？")
print("=" * 70)

print("\n1. 先看一个普通的 attribute（属性）")
print("-" * 70)

# tagName 是一个普通属性
print(f"t_element.tagName = {t_element.tagName}")
print(f"tagName 的类型: {type(t_element.tagName)}")
print(f"tagName 是 attribute 吗？ {hasattr(t_element, 'tagName')}")
print(f"tagName 可以调用吗（加括号）？ {callable(t_element.tagName)}")

print("\n2. 再看一个 method（方法）")
print("-" * 70)

# toxml 是一个方法
print(f"t_element.toxml = {t_element.toxml}")
print(f"toxml 的类型: {type(t_element.toxml)}")
print(f"toxml 是 attribute 吗？ {hasattr(t_element, 'toxml')}")
print(f"toxml 可以调用吗（加括号）？ {callable(t_element.toxml)}")

print("\n" + "=" * 70)
print("关键发现：")
print("=" * 70)

print("""
1. tagName 是普通属性：
   - hasattr() 返回 True
   - callable() 返回 False  ← 不能加括号调用
   - 类型是 str

2. toxml 是方法：
   - hasattr() 返回 True  ← 方法也是属性！
   - callable() 返回 True  ← 可以加括号调用
   - 类型是 method 或 function
""")

print("\n" + "=" * 70)
print("结论：Method 是一种特殊的 Attribute")
print("=" * 70)

print("""
在 Python 中：
- Attribute（属性）= 对象身上的任何东西
  - 可以是数据（tagName = "w:t"）
  - 也可以是方法（toxml = <method>）

- Method（方法）= 可以调用的 Attribute
  - 是 Attribute 的子集
  - 特点：callable() 返回 True
  - 可以加括号 () 执行
""")

print("\n" + "=" * 70)
print("实际演示：区别在于能不能调用")
print("=" * 70)

print("\n尝试 1：访问普通属性")
print(f"t_element.tagName → {t_element.tagName}")

print("\n尝试 2：访问方法（不加括号）")
print(f"t_element.toxml → {t_element.toxml}")
print("  ↑ 得到的是方法对象本身，还没执行")

print("\n尝试 3：调用方法（加括号）")
result = t_element.toxml()
print(f"t_element.toxml() → {result}")
print("  ↑ 加了括号，方法被执行，返回结果")

print("\n尝试 4：如果对普通属性加括号会怎样？")
try:
    t_element.tagName()
    print("成功")
except TypeError as e:
    print(f"报错！{e}")
    print("  ↑ 因为 tagName 是字符串，不是方法，不能调用")

print("\n" + "=" * 70)
print("所以 hasattr() 可以检查两种东西：")
print("=" * 70)

print(f"""
hasattr(t_element, 'tagName')  → {hasattr(t_element, 'tagName')}  (普通属性)
hasattr(t_element, 'toxml')    → {hasattr(t_element, 'toxml')}  (方法)
hasattr(t_element, 'blahblah') → {hasattr(t_element, 'blahblah')}  (不存在)

hasattr() 的意思是：
"这个对象有没有这个名字的属性（不管是数据还是方法）"
""")

print("\n" + "=" * 70)
print("如何区分 Attribute 是不是 Method？")
print("=" * 70)

print(f"""
用 callable() 函数：

callable(t_element.tagName) → {callable(t_element.tagName)}  (False = 不是方法)
callable(t_element.toxml)   → {callable(t_element.toxml)}  (True = 是方法)
""")

print("\n" + "=" * 70)
print("总结图示")
print("=" * 70)

print("""
┌─────────────────────────────────────┐
│     Attribute（属性）                 │
│  对象身上的所有东西                    │
│                                     │
│  ┌──────────────┐  ┌─────────────┐ │
│  │ 数据属性      │  │  方法       │ │
│  │ (Data)       │  │ (Method)    │ │
│  │              │  │             │ │
│  │ tagName      │  │ toxml()     │ │
│  │ nodeType     │  │ getAttribute()│ │
│  │ nodeValue    │  │ appendChild() │ │
│  │              │  │             │ │
│  │ callable()   │  │ callable()  │ │
│  │ = False      │  │ = True      │ │
│  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────┘

hasattr() 可以检查两种
callable() 只对方法返回 True
""")
