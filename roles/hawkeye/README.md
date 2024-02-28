# Hawkeye Prometheus Role

A ansible role for installing, configuring and upgrading Prometheus server.
It also setup a confd service container to generate Prometheus alert, record rules, and
Prometheus scrape targets via Prometheus file service discovery.

## Requirements

* Docker daemon and container images was ready.

## Role Variables

* `hawkeye_distribution`
    * Uses to identify which OpenStack distribution was installed.
    * Valid options are '**uos5**' and '**osp13**'.
    * Defaults is '**uos5**'.

## Example Playbook

```yaml
- hosts:
    - hawkeye
    - prometheus
    - alertmanager
    - cadvisor
    - node_exporters
    - blackbox_exporter
    - haproxy_exporter
    - memcached_exporter
    - mysqld_exporter
    - redis_exporter
    - grafana
  roles:
    - role: hawkeye
      tags: hawkeye
      when:
        - enable_hawkeye | bool
```

## License

&copy; 2018-2019 The Hawkeye Authors. All Rights Reserved.

This Ansible role is licensed under Apache 2.0 license that can be found in the [LICENSE](../../../LICENSE) file.
