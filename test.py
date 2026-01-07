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
paras = dom.getElementsByTagName('w:p')
runs = dom.getElementsByTagName('w:r')
texts = dom.getElementsByTagName('w:t')

para1 = paras[0]
run1 = runs[0]
text1= texts[0]

for text in texts:
    print(type(text), type(text.firstChild), type(text.firstChild.nodeValue))
    print(text)
    print(text.firstChild)
    print(text.firstChild.nodeValue)
    print(text.toxml())
    print(text.firstChild.toxml())