# FFL Examples — `groupphoto`

Every numbered scenario is a **complete, compilable FFL file**. Copy one into
`my.ffl` and run it:

```bash
fw ffl run --primary my.ffl \
  --library ~/fw_handlers/fwh_groupphoto/src/groupphoto/ffl/groupphoto.ffl \
  --workflow my.groupphoto.<WorkflowName>
```

A runner serving the `groupphoto` namespace must be up
(`fw runner start --domain groupphoto`). Every block below is compile-checked
against `src/groupphoto/ffl/groupphoto.ffl`.

New to the language? Start with the
[FFL grammar](https://github.com/rlemke/facetwork/blob/main/docs/reference/language/grammar.md)
and the [canonical examples](https://github.com/rlemke/facetwork/tree/main/examples/canonical).

---

## The facets at a glance

A list step that enumerates work, a per-image step that does it, and workflows
that fan the second out over the first. That "list → fan-out" shape is the whole
domain, and it generalises to any batch of files.

| Declaration | Signature | Does |
|---|---|---|
| `groupphoto.Ingest.ListImages` | `(in_dir: String) => (paths: Json, count: Long)` | Enumerate images — the fan-out unit |
| `groupphoto.Ingest.ConvertRaw` | `(image_path, out_dir, highlight_mode = "clip") => (output)` | One RAW → one converted file |
| `groupphoto.Ingest.ConvertTree` | `(in_dir, out_dir, out_format, resize, from_sel, recursive, quality, workers) => (converted, skipped, failed)` | Whole-tree convert in one step |
| `groupphoto.Ingest.CopyTree` | `(src, dst, workers) => (copied, skipped, failed)` | Whole-tree copy |
| `groupphoto.Enhance.EnhanceGroup` | `(image_path, out_dir, background = "none", out_format = "tiff", highlight_mode = "clip") => (output, n_people)` | One posed group photo → one enhanced output |
| `groupphoto.Enhance.ReplaceBackground` | `(image_path, out_dir, mode = "blur", bg_image = "") => (output)` | Background swap on its own |
| `groupphoto.workflows.EnhanceOne` / `EnhanceBatch` / `ConvertBatch` / `ConvertDir` / `CopyDir` | The shipped entry points |

---

## 1. Run what ships — no FFL to write

```bash
fw ffl seed --include groupphoto

# one photo
fw ffl run --primary ~/fw_handlers/fwh_groupphoto/src/groupphoto/ffl/groupphoto.ffl \
  --workflow groupphoto.workflows.EnhanceOne \
  --inputs '{"image_path": "/data/photos/group.NEF", "out_dir": "/data/out"}'

# a whole directory of RAWs → TIFF
fw ffl run --primary …/groupphoto.ffl --workflow groupphoto.workflows.ConvertDir \
  --inputs '{"in_dir": "/data/raw", "out_dir": "/data/tif", "out_format": "tif"}'
```

Write FFL when you want a different *shape* — convert then enhance in one run,
your own error handling, or per-photo options.

## 2. The smallest workflow you can write

Every FFL workflow needs a `namespace`, a `use` per namespace it calls into, and a
`yield` back to itself.

```ffl
namespace my.groupphoto {

    use groupphoto.Enhance

    /** One posed group photo → one enhanced output. */
    workflow OnePhoto(image_path: String, out_dir: String) => (output: String, people: Long) andThen {

        e = groupphoto.Enhance.EnhanceGroup(image_path = $.image_path, out_dir = $.out_dir)

        yield OnePhoto(output = e.output, people = e.n_people)
    }
}
```

Rules visible above: `=>` sits on the **same line** as the closing `)`; references
are always `step.field`; `$.image_path` reads the workflow's parameter.

## 3. Fan out over a directory — list, then `foreach`

`andThen foreach v in <list>` turns one step into N runtime steps that runners
claim in parallel. Because the `foreach` hangs off the **`listed` step**, inside the
body `$` is that step (so `$.p` is the loop variable) and `$$` reaches the
workflow's parameters.

```ffl
namespace my.groupphoto {

    use groupphoto.Ingest
    use groupphoto.Enhance

    /** Enumerate a directory, then enhance every photo in parallel. */
    workflow EnhanceDir(in_dir: String, out_dir: String, background: String = "blur") => (count: Long) andThen {

        listed = groupphoto.Ingest.ListImages(in_dir = $.in_dir) andThen foreach p in $.paths {

            done = groupphoto.Enhance.EnhanceGroup(
                image_path = $.p, out_dir = $$.out_dir, background = $$.background)

            yield EnhanceDir(count = 1)
        }
    }
}
```

Wall clock is the slowest photo, not the sum — add runners to go faster.

## 4. Fan out over *your own* list

The list doesn't have to come from a facet. Take it as a `Json` parameter and the
selection becomes a CLI argument. Here the `foreach` hangs off the **workflow**, so
the loop variable and the workflow's parameters share one `$`.

```ffl
namespace my.groupphoto {

    use groupphoto.Enhance

    /** Enhance exactly the photos you name. */
    workflow EnhanceChosen(paths: Json, out_dir: String) => (count: Long) andThen foreach p in $.paths {

        done = groupphoto.Enhance.EnhanceGroup(
            image_path = $.p,
            out_dir = $.out_dir,
            background = "none",
            out_format = "tiff")

        yield EnhanceChosen(count = 1)
    }
}
```

```bash
fw ffl run --primary my.ffl --library …/groupphoto.ffl \
  --workflow my.groupphoto.EnhanceChosen \
  --inputs '{"paths": ["/data/a.NEF", "/data/b.NEF"], "out_dir": "/data/out"}'
```

## 5. Chain two per-image steps

Steps compose within a loop body: enhance, then swap the background of the
enhanced output by referencing `e.output`.

```ffl
namespace my.groupphoto {

    use groupphoto.Ingest
    use groupphoto.Enhance

    /** Enhance, then replace the background of each result. */
    workflow EnhanceThenSwap(in_dir: String, out_dir: String, bg_image: String = "") => (count: Long) andThen {

        listed = groupphoto.Ingest.ListImages(in_dir = $.in_dir) andThen foreach p in $.paths {

            e = groupphoto.Enhance.EnhanceGroup(image_path = $.p, out_dir = $$.out_dir)

            swapped = groupphoto.Enhance.ReplaceBackground(
                image_path = e.output,
                out_dir = $$.out_dir,
                mode = "image",
                bg_image = $$.bg_image)

            yield EnhanceThenSwap(count = 1)
        }
    }
}
```

`swapped` references `e.output`, which is what orders it after the enhance — line
order alone would not.

## 6. One corrupt file shouldn't kill the batch — `catch`

`catch` fires when its step errors after retries are exhausted. Inside a `foreach`
it is per-iteration, so the rest of the batch proceeds.

```ffl
namespace my.groupphoto {

    use groupphoto.Ingest
    use groupphoto.Enhance

    /** Best-effort batch: skip the photos that blow up. */
    workflow BestEffortDir(in_dir: String, out_dir: String) => (count: Long) andThen {

        listed = groupphoto.Ingest.ListImages(in_dir = $.in_dir) andThen foreach p in $.paths {

            done = groupphoto.Enhance.EnhanceGroup(image_path = $.p, out_dir = $$.out_dir) catch {
                yield BestEffortDir(count = 0)
            }

            yield BestEffortDir(count = 1)
        }
    }
}
```

## 7. Branch on a result — `when`

A `when` block hangs off the step it inspects: inside a case `$` is that step and
`$$` reaches the workflow. Every `when` needs a default case, last.

```ffl
namespace my.groupphoto {

    use groupphoto.Ingest

    /** Only convert if the directory actually has images. */
    workflow GuardedConvert(in_dir: String, out_dir: String, min_images: Long = 1) => (status: String, converted: Long) andThen {

        listed = groupphoto.Ingest.ListImages(in_dir = $.in_dir) andThen when {
            case $.count >= $$.min_images => {
                conv = groupphoto.Ingest.ConvertTree(
                    in_dir = $$.in_dir, out_dir = $$.out_dir, out_format = "tif")
                yield GuardedConvert(status = "converted", converted = conv.converted)
            }
            case _ => {
                yield GuardedConvert(status = "empty_dir", converted = 0)
            }
        }
    }
}
```

## 8. Call-time mixins — timeouts and retries

Long RAW conversions are exactly the case for a call-site override:

```ffl
namespace my.groupphoto {

    use groupphoto.Ingest

    /** A big tree needs more than the default budget. */
    workflow PatientConvert(in_dir: String, out_dir: String) => (converted: Long) andThen {

        conv = groupphoto.Ingest.ConvertTree(
            in_dir = $.in_dir, out_dir = $.out_dir, out_format = "tif") with Timeout(minutes = 240) with Retry(maxAttempts = 2, backoffSeconds = 60)

        yield PatientConvert(converted = conv.converted)
    }
}
```

## 9. Reuse the shipped workflows

```ffl
namespace my.groupphoto {

    use groupphoto.workflows

    /** Wrap the shipped batch workflow. */
    workflow BatchWithCount(paths: Json, out_dir: String) => (count: Long) andThen {

        run = groupphoto.workflows.EnhanceBatch(paths = $.paths, out_dir = $.out_dir, background = "blur")

        yield BatchWithCount(count = run.count)
    }
}
```

---

## Cheat sheet

| You want to… | Write |
|---|---|
| Read a workflow/step parameter | `$.name` (`$$.name` one level out) |
| Read a previous step's result | `stepname.field` |
| Fan out from a facet's list result | `step = List(…) andThen foreach v in $.field { … }` (then `$$` = workflow) |
| Fan out from a CLI list | `workflow W(items: Json) … andThen foreach i in $.items { … }` (`$` = workflow) |
| Order two steps | reference a field of the first from the second |
| More time / retries for one call | `… with Timeout(minutes = 240) with Retry(maxAttempts = 2, backoffSeconds = 60)` |
| Handle a step failure | `step = Facet(…) catch { yield … }` |
| Branch | `step = Facet(…) andThen when { case <bool> => { … } case _ => { … } }` |
| Concatenate strings | `a ++ b` |

**Validate before you run:** `afl my.ffl --check` or MCP `fw_validate`. Every error
carries a `rule_id` — fetch `fw://docs/rules/{rule_id}` for a wrong/right pair.

## See also

- [`docs/README.md`](README.md) — per-feature specs for this domain
- [FFL grammar](https://github.com/rlemke/facetwork/blob/main/docs/reference/language/grammar.md) ·
  [canonical examples](https://github.com/rlemke/facetwork/tree/main/examples/canonical) ·
  [relative `$`-scoping](https://github.com/rlemke/facetwork/blob/main/docs/architecture/ffl-relative-scoping.md)
- `src/groupphoto/ffl/groupphoto.ffl` — the source of truth for every signature above
