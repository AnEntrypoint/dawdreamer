# Kaggle runner

Sends a `.py` or `.ipynb` file to Kaggle as a kernel, waits for it to finish, and downloads what it wrote. Standard library Python only; the `kaggle` CLI (tested with 2.2.5) does the network work.

## Setup (once per machine)

`pip install kaggle`, put `kaggle` on PATH, and keep the API token in `~/.kaggle/credentials.json` (mode 600). The runner never opens that file and passes no credentials on the command line; the CLI reads them itself.

## Submit a job

    python3 tools/kaggle/kaggle_run.py path/to/job.py OWNER/kernel-slug [--timeout 3600] [--internet]

- `OWNER` is your Kaggle username. The slug is lowercase letters, digits and hyphens, and the kernel title is set to the slug.
- The kernel is private. Internet is off unless `--internet` is given.
- `--dry-run` prints the generated `kernel-metadata.json` and pushes nothing.
- Smoke test: `python3 tools/kaggle/kaggle_run.py tools/kaggle/probe_env.py heclgang/dawdreamer-kaggle-probe` reports the kernel's Python version, CPU count and memory.

## Output

`tools/kaggle/out/<slug>/<UTC stamp>/` (git-ignored) holds:

- everything the job wrote to `/kaggle/working`, so write results there;
- `kernel.log`, the raw JSON stream from `kaggle kernels logs` (the text is in each entry's `data` field);
- `run.json`, with the kernel URL, final state and file list.

## Time limit

- `--timeout` (default 3600 s) is the kernel run limit passed to `kaggle kernels push -t`.
- `--max-wait` (default timeout + 900 s) is how long the runner polls before it stops waiting. The kernel can keep running after that.
- Kaggle also caps session length on its side. Sources disagree (9 h or 12 h), so check https://www.kaggle.com/docs/notebooks before relying on a number.

## Exit codes

0 complete · 1 kernel error, cancel or push failure · 2 bad usage · 3 gave up waiting.
