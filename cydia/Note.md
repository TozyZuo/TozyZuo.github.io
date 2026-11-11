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

注：Release 文件为整个Cydia源的描述。

### 名将杀与三国杀 Rootless 插件维护（2026-11-11）

本源额外提供两款游戏的**越狱版**插件，LC 的 `.dylib` 不属于可直接经 Cydia 安装的包：

- `local.mjs.appearance` 0.5.3：名将杀本地外观，`iphoneos-arm64`，依赖 ElleKit；安装前应完整退出游戏。
- `local.sgs.appearance` 0.4.0：三国杀本地外观，`iphoneos-arm64`，依赖 ElleKit；使用与 LC 版共用的 Lua 适配核心。目前 **14pm 实装验收尚未完成**，请保留原游戏数据备份。

新增或更新这两款游戏 DEB 后，在**本仓库根目录**执行：

```bash
python3 cydia/update_game_packages.py \
  cydia/debs/MJSLocalAppearance_0.5.3_iphoneos-arm64.deb \
  cydia/debs/SGSLocalAppearance_0.4.0_iphoneos-arm64.deb
```

该脚本读取 DEB 内的真实 `Package`、`Version`、`Architecture`、`Depends` 和注入过滤配置，检查目标 App，再更新 `Packages` 与 `Packages.bz2`；会逐条核实索引中**所有安装包**的大小和散列值，不会覆盖或删除其他插件。它只更新本地文件，不会自动执行 Git push。`Release` 的仓库身份与架构没有变更时无需重写。

名将杀当前 0.5.3 DEB 内还包含两份游戏 Logic 原始编码文件（包体约 14 MB）；如需对公开分发的版权许可作更严格的审查，应先评估或改为不附带该数据的包，再发布。


### Deb解包封包

`dpkg -X xxx.deb extract/`

`dpkg -e xxx.deb extract/DEBIAN/ `

`dpkg-deb -b extract xxx.deb`