# MAINE：统一的云部署工具

Maine 是由同方有云开发的新一代、统一的云部署工具，支持 UOS、UDS、Hawkeye 等产品的独立或组合部署。

## 规划

* 杂项
  * 开发文档、部署文档、建议性运维文档
  * CI 测试逻辑（本地、远程）
* 核心依赖
  * 节点防火墙端口管理
  * 时钟同步
* 基础组件
  * HAProxy
  * 组件 HAProxy 灵活配置管理
  * （可选）Mariadb
  * （可选）RabbitMQ
  * （可选）Memcached
  * （可选）Redis
  * （可选）Etcd（默认使用 V3 API）
* OpenStack 核心服务
  * Keystone
  * Glance
  * Neutron、Open vSwitch、Octavia
  * Nova
  * Cinder
* OpenStack 附加服务
  * Aodh、Ceilometer、Gnocchi、Panko
  * Cloudkitty
  * Heat
  * Horizon
  * Ironic
  * Manila
  * Masakari
  * Mistral
  * Zaqar
* UOS
  * Kunkka
  * Mirana
  * Shadowfiend
* Ceph
  * Ceph 块存储
  * Ceph 对象存储
  * Ceph 文件存储
* Hawkeye
  * Prometheus
  * Alertmanager
  * Node Exporter

> （可选）：表示可采用外部已经部署好的服务。

## 开发

### 代码测试

1、 代码风格检查

```shell
tox -e pep8
```

2、 Python 代码测试

```shell
tox -e py27,py36
```

### 部署测试

参考《部署文档》中“[虚拟环境](http://uos-installation-guide-docs.apps.ustack.com/appendix/virtual-environments.html)”章节。

### 代码提交

本项目采用 [Gerrit](https://review.ustack.com) 进行代码审核。提交代码前，请在本地一次 `tox` 测试，确保全部通过后，再提交到 Gerrit。

```shell
git review [-t your topic] [target branch]
```

> Gerrit 使用请参考 [Infra 文档](http://infra-docs.apps.ustack.com/user-guide/gerrit/index.html)。

## 版权

&copy; 2018-2021 同方有云

详细信息见本项目的 [LICENSE](LICENSE) 文件。
