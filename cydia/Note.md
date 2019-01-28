### Cydia搭建及维护的方法
具体的搭建方法不多说了，基本是参考这个视频：<http://www.youtube.com/watch?v=9eHKvCqBDBQ>

主要记录一下如何添加和更新.deb文件

1. 将所有的.deb文件放到 /repo/debs 文件夹中

2. 在【终端】里输入命令

	`cd repo`

3. 继续输入命令

	`dpkg-scanpackages debs / > Packages`

4. 第3步生成了集合所有deb文件信息的 Packages 文件

5. 利用 bzip2 生成 Cydia 可以识别的文件格式，输入命令

	`bzip2 -fks Packages`

6. 将所有文件上传到服务器即可

注：Release 文件为整个Cydia源的描述