# Templates (quickstart)

These YAML files are minimal starting points. They are designed to run fast
and avoid interactive plotting.

Single-date (fast):
```
pyages run examples/templates/quickstart_single.yaml
```

Multi-date / temporal (fast):
```
pyages run --transient examples/templates/quickstart_temporal.yaml
```

Tip: you can override key fields from the CLI:
```
pyages run --lpm exp_shifted --mh-nsteps 5000 --data-name mydata.txt --data-dir examples/my_site/data examples/templates/quickstart_single.yaml
pyages run --transient --lpm ig --mh-nsteps 500 --data-file examples/my_site/data/ori_my_site_2005_2024.txt examples/templates/quickstart_temporal.yaml
```
