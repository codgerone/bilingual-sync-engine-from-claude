#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示 DOM 对象的结构和内容
"""

from defusedxml import minidom

# 示例XML - 一个简单的Word文档片段
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
            <w:ins w:id="1" w:author="美琦">
                <w:r>
                    <w:t>不错</w:t>
                </w:r>
            </w:ins>
        </w:p>
    </w:body>
</w:document>
"""

print("=" * 80)
print("1. 解析XML字符串")
print("=" * 80)

# 解析
dom = minidom.parseString(xml_string)

print(f"\ndom 对象的类型: {type(dom)}")
print(f"dom 对象: {dom}")

print("\n" + "=" * 80)
print("2. DOM对象的基本信息")
print("=" * 80)

print(f"\n节点类型 (nodeType): {dom.nodeType}")
print(f"节点类型常量 (DOCUMENT_NODE): {dom.DOCUMENT_NODE}")
print(f"是否是文档节点: {dom.nodeType == dom.DOCUMENT_NODE}")

print(f"\n节点名称 (nodeName): {dom.nodeName}")
print(f"节点值 (nodeValue): {dom.nodeValue}")

print("\n" + "=" * 80)
print("3. DOM对象的结构（用 toxml() 查看）")
print("=" * 80)

# toxml() 可以把DOM对象转回XML字符串
print("\ndom.toxml() 输出（完整XML）:")
print(dom.toxml()[:500] + "...\n")  # 只显示前500个字符

print("\n" + "=" * 80)
print("4. DOM对象的根元素 (documentElement)")
print("=" * 80)

root = dom.documentElement
print(f"\n根元素: {root}")
print(f"根元素类型: {type(root)}")
print(f"根元素标签名: {root.tagName}")
print(f"根元素节点类型: {root.nodeType} (ELEMENT_NODE={root.ELEMENT_NODE})")

print("\n" + "=" * 80)
print("5. DOM对象的所有子节点")
print("=" * 80)

print(f"\ndom.childNodes: {dom.childNodes}")
print(f"子节点数量: {len(dom.childNodes)}")

for i, child in enumerate(dom.childNodes):
    print(f"\n子节点 {i}:")
    print(f"  - 类型: {child.nodeType}")
    print(f"  - 名称: {child.nodeName}")
    if child.nodeType == child.ELEMENT_NODE:
        print(f"  - 标签名: {child.tagName}")
    else:
        print(f"  - 值: {repr(child.nodeValue)}")

print("\n" + "=" * 80)
print("6. 深入查看DOM树的结构")
print("=" * 80)

def print_tree(node, indent=0):
    """递归打印DOM树的结构"""
    prefix = "  " * indent
    
    if node.nodeType == node.ELEMENT_NODE:
        # 元素节点
        attrs = []
        if hasattr(node, 'attributes') and node.attributes:
            for i in range(node.attributes.length):
                attr = node.attributes.item(i)
                attrs.append(f'{attr.name}="{attr.value}"')
        
        if attrs:
            print(f"{prefix}<{node.tagName} {' '.join(attrs)}>")
        else:
            print(f"{prefix}<{node.tagName}>")
        
        # 递归打印子节点
        for child in node.childNodes:
            print_tree(child, indent + 1)
        
        print(f"{prefix}</{node.tagName}>")
    
    elif node.nodeType == node.TEXT_NODE:
        # 文本节点
        text = node.nodeValue.strip()
        if text:  # 只显示非空文本
            print(f"{prefix}[文本: {repr(text)}]")
    
    elif node.nodeType == node.DOCUMENT_NODE:
        # 文档节点
        print(f"{prefix}[Document]")
        for child in node.childNodes:
            print_tree(child, indent + 1)

print("\nDOM树的完整结构:")
print_tree(dom)

print("\n" + "=" * 80)
print("7. 使用 DOM 方法查找元素")
print("=" * 80)

# 查找所有段落
paragraphs = dom.getElementsByTagName('w:p')
print(f"\n找到 {len(paragraphs)} 个段落 (w:p)")

# 查找所有删除
deletions = dom.getElementsByTagName('w:del')
print(f"找到 {len(deletions)} 个删除 (w:del)")

# 查找所有插入
insertions = dom.getElementsByTagName('w:ins')
print(f"找到 {len(insertions)} 个插入 (w:ins)")

# 查找所有文本
texts = dom.getElementsByTagName('w:t')
print(f"找到 {len(texts)} 个文本元素 (w:t)")

print("\n" + "=" * 80)
print("8. 提取具体的内容")
print("=" * 80)

if deletions:
    deletion = deletions[0]
    print(f"\n第一个删除标记:")
    print(f"  - 作者: {deletion.getAttribute('w:author')}")
    print(f"  - 日期: {deletion.getAttribute('w:date')}")
    print(f"  - ID: {deletion.getAttribute('w:id')}")
    
    # 找到删除的文本
    del_texts = deletion.getElementsByTagName('w:delText')
    if del_texts and del_texts[0].firstChild:
        print(f"  - 删除的内容: {del_texts[0].firstChild.nodeValue}")

if insertions:
    insertion = insertions[0]
    print(f"\n第一个插入标记:")
    print(f"  - 作者: {insertion.getAttribute('w:author')}")
    print(f"  - ID: {insertion.getAttribute('w:id')}")
    
    # 找到插入的文本
    ins_texts = insertion.getElementsByTagName('w:t')
    if ins_texts and ins_texts[0].firstChild:
        print(f"  - 插入的内容: {ins_texts[0].firstChild.nodeValue}")

print("\n" + "=" * 80)
print("9. DOM对象的所有可用属性和方法")
print("=" * 80)

print("\nDocument 对象的重要属性:")
important_attrs = [
    'nodeType', 'nodeName', 'nodeValue', 
    'childNodes', 'firstChild', 'lastChild',
    'documentElement', 'getElementsByTagName'
]

for attr in important_attrs:
    if hasattr(dom, attr):
        value = getattr(dom, attr)
        if callable(value):
            print(f"  - {attr}: <方法>")
        else:
            print(f"  - {attr}: {value}")

print("\n所有属性和方法（部分）:")
all_attrs = [attr for attr in dir(dom) if not attr.startswith('_')]
print(f"  共有 {len(all_attrs)} 个公开属性/方法")
print(f"  前20个: {', '.join(all_attrs[:20])}")

print("\n" + "=" * 80)
print("完成！")
print("=" * 80)