from cProfile import Profile as pfile
from pstats import Stats
from io import StringIO 
from os import system, makedirs, path

class Profile:
    def __init__(self):
        self.pr = pfile()
    def start(self):
        self.pr.enable()
    def end(self, filename):
        self.pr.disable()
        output_dir = "ProfileResults"
        makedirs(output_dir, exist_ok=True)
        
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