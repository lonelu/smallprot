## activate the conda environment. conda activate env_smallprot
## please check/change the parameters in 'parameter_loop_truc.ini' 
## you can use ipython or just 'python run_rocker.py'
import sys
sys.path.append(r'/mnt/e/GitHub_Design/Qbits')
sys.path.append(r'/mnt/e/GitHub_Design/smallprot')

print('Thanks for using smallprot!')

from smallprot import smallprot 

seed_pdb = '/mnt/e/GitHub_Design/smallprot/data/rocker/seed_correct.pdb'
query_pdb = None
exclusion_pdb = None

workdir = '/mnt/e/GitHub_Design/smallprot/data/rocker/output_build'
para = '/mnt/e/GitHub_Design/smallprot/parameter_loop_truc_rocker.ini'

hhh = smallprot.SmallProt(seed_pdb, query_pdb, exclusion_pdb,  workdir, para)
# n_truncations=list(range(20))
# c_truncations=list(range(10))
n_truncations = [1, 2, 3]
c_truncations = [1, 2]
hhh.loop_structure(n_truncations = n_truncations, c_truncations = c_truncations)