from cProfile import Profile as pfile
from pstats import Stats
from io import StringIO 
from os import system, makedirs, path

class Profiler:
    """
    Profiler
    A small helper class that wraps a profiler instance and collects, formats,
    and exports profiling results for a given filename.
    Attributes
    - pr: profiler instance created by calling pfile(). Expected to expose
        enable()/disable() and to be consumable by pstats.Stats.
    Methods
    - ```start()```
        Enable the profiler (calls ```pr.enable()```).
    - ```end(filename)```
        Stop profiling (calls ```pr.disable()```), create an output directory named
        "ProfileResults" (```makedirs(..., exist_ok = True)```), and write three outputs
        derived from the provided filename:
            * A human-readable text report: "<name_without_ext>.txt"
                (printed to stdout and saved to the file).
            * A dumped profiler data file: "<base_name>" (exact base filename preserved).
            * A flame graph SVG: "<name_without_ext>.svg" produced by running
                ``python -m flameprof {prof_path} > {svg_path}`` (requires flameprof).
    Behavior and dependencies
    - Uses a StringIO buffer to capture ```Stats(...).print_stats()``` output and
        writes that buffer both to stdout and to the .txt file.
    - Uses ```pstats.Stats``` (or equivalent) to sort by cumulative time ("cumtime")
        before printing and dumping stats.
    - Expects the following names/imports to be available in the module:
        pfile, makedirs, path (```os.path```), StringIO (```io.StringIO```), Stats (```pstats.Stats```),
        and system (```os.system```) or equivalent.
    - No explicit error handling: file operations or external command calls may
        raise exceptions; files may be overwritten.
    Usage notes
    - Call ```start()``` before the code region to profile and ```end(filename)``` after.
    - filename should include the extension .prof
    - Ensure flameprof is installed in the Python environment if SVG output is desired.
    """

    def __init__(self):
        self.pr = pfile()
    def start(self):
        self.pr.enable()
    def end(self, filename):
        self.pr.disable()
        output_dir = "ProfileResults"
        makedirs(output_dir, exist_ok = True)
        
        base_name = path.basename(filename)
        name_without_ext = path.splitext(base_name)[0]

        txt_path = path.join(output_dir, f"{name_without_ext}.txt")
        prof_path = path.join(output_dir, base_name)
        svg_path = path.join(output_dir, f"{name_without_ext}.svg")

        s = StringIO()
        sortby = "cumtime" 
        ps = Stats(self.pr, stream = s).sort_stats(sortby)
        ps.print_stats()
        print(s.getvalue())

        with open(txt_path, "w") as f:
            f.write(s.getvalue())
 
        ps.dump_stats(prof_path)

        system(f"python -m flameprof {prof_path} > {svg_path}")