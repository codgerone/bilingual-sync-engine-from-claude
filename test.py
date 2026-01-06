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

dom = minidom.parseString(xml_string)
runs = dom.getElementsByTagName('w:r')
first_run = runs[0]
t_element = first_run.getElementsByTagName('w:t')
first_text_element_of_first_run = t_element[0]
text1 = first_text_element_of_first_run.firstChild

print(type(runs), runs.toxml())
print(type(first_run), first_run.toxml())
print(type(t_element), t_element.toxml())
print(type(first_text_element_of_first_run), first_text_element_of_first_run.toxml())
print(type(text1), text1.toxml())

print(f"text1 nodeType: {text1.nodeType}, nodeName: {text1.nodeName}, nodeValue: {text1.nodeValue}")
print(f"Is text1 a TEXT_NODE? {text1.nodeType == text1.TEXT_NODE}")