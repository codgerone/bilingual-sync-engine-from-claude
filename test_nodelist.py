from defusedxml import minidom

xml_string = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p>
            <w:r>
                <w:t>今天天气</w:t>
            </w:r>
            <w:del w:id="0" w:author="美琦" w:date="2025-11-07T15:28:00Z">
                <w:r>
                    <w:delText>很好</w:delText>
                </w:r>
            </w:del>
        </w:p>
    </w:body>
</w:document>
"""

# 解析
dom = minidom.parseString(xml_string)

print("=" * 60)
print("1. 对象类型对比")
print("=" * 60)

# dom 的类型
print(f"\ndom 的类型: {type(dom)}")
print(f"dom 的类名: {type(dom).__name__}")

# runs 的类型
runs = dom.getElementsByTagName('w:r')
print(f"\nruns 的类型: {type(runs)}")
print(f"runs 的类名: {type(runs).__name__}")

# t_element 的类型
t_element = runs[0].getElementsByTagName('w:t')[0]
print(f"\nt_element 的类型: {type(t_element)}")
print(f"t_element 的类名: {type(t_element).__name__}")

print("\n" + "=" * 60)
print("2. getElementsByTagName 是什么？")
print("=" * 60)

print(f"\ngetElementsByTagName 是方法吗？ {callable(dom.getElementsByTagName)}")
print(f"它的类型: {type(dom.getElementsByTagName)}")

print("\n" + "=" * 60)
print("3. NodeList 是什么样的？")
print("=" * 60)

print(f"\nruns 对象本身: {runs}")
print(f"runs 的长度: {len(runs)}")
print(f"runs 可以用索引访问吗？试试 runs[0]: {runs[0]}")
print(f"runs[0] 的类型: {type(runs[0])}")

# NodeList 像列表一样可以遍历
print("\nNodeList 可以遍历：")
for i, run in enumerate(runs):
    print(f"  第 {i} 个元素: {run.tagName}")

print("\n" + "=" * 60)
print("4. toxml() 方法对比")
print("=" * 60)

# Document 对象有 toxml()
print(f"\ndom 有 toxml() 方法吗？ {hasattr(dom, 'toxml')}")
if hasattr(dom, 'toxml'):
    print("dom.toxml() 的前100个字符:")
    print(dom.toxml()[:100])

# Element 对象有 toxml()
print(f"\nt_element 有 toxml() 方法吗？ {hasattr(t_element, 'toxml')}")
if hasattr(t_element, 'toxml'):
    print("t_element.toxml():")
    print(t_element.toxml())

# NodeList 有 toxml() 吗？
print(f"\nruns (NodeList) 有 toxml() 方法吗？ {hasattr(runs, 'toxml')}")

# 但是 NodeList 里面的每个元素有 toxml()
print("\n但是可以对 NodeList 里的每个元素调用 toxml():")
for i, run in enumerate(runs):
    print(f"\nruns[{i}].toxml():")
    print(run.toxml())

print("\n" + "=" * 60)
print("5. 总结：三种对象的区别")
print("=" * 60)

print("""
1. Document 对象 (dom)
   - 代表整个 XML 文档
   - 有 toxml() 方法
   - 有 getElementsByTagName() 方法

2. Element 对象 (t_element)
   - 代表一个 XML 元素（标签）
   - 有 toxml() 方法
   - 有 getElementsByTagName() 方法
   - 有 tagName 属性

3. NodeList 对象 (runs)
   - 是一个"列表"，包含多个 Element
   - 没有 toxml() 方法 ← 关键！
   - 可以用 len(), 索引 [0], 遍历
   - 类似 Python 的 list，但不完全一样
""")
