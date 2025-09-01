
# What is Volume Z-Score?

**Definition:** Standardize current volume vs a rolling 60-min mean/std.

```
Z = (vol_now - mean_60m) / std_60m
```

**Use:** Filter fake pumps — prefer **Z ≥ 1.5**, strong **Z ≥ 2.0**.
