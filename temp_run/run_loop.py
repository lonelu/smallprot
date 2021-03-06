## activate the conda environment. conda activate env_smallprot
## please check/change the parameters and file paths according to your purpose.
## you can use ipython or just 'python run_loop.py'
import sys
sys.path.append(r'/mnt/e/GitHub_Design/Qbits')
sys.path.append(r'/mnt/e/GitHub_Design/smallprot')

print('Thanks for using smallprot!')

from smallprot import smallprot_config, loop_sse

para = smallprot_config.Parameter(
        ###Database
        database='/mnt/e/GitHub_Design/Qbits/database',
        loop_target_list='/mnt/e/GitHub_Design/master_db/list',   
        ###For loop searching     
        master_query_loop_top = 200,
        max_nc_dist = 16.0,
        loop_query_win =7,   
        min_loop_length = 3,
        max_loop_length=20,
        select_min_rmsd_pdb = True,
        cluster_count_cut=20,
        loop_distance_cut=15,
        construct_keep = 0
)


seed_pdb = '/mnt/e/DesignData/smallprot_loops/nina/seed.pdb'
query_pdb = None
exclusion_pdb = None

workdir = '/mnt/e/DesignData/smallprot_loops/nina/output_test_build2/'


hhh = loop_sse.Loop_sse(seed_pdb, query_pdb, exclusion_pdb,  workdir, para)
# n_truncations=list(range(20))  ## from 0 to 19
# c_truncations=list(range(10))  ## from 0 to 9
# n_truncations = [16, 17, 18, 19]
# c_truncations = [1, 2, 3, 4, 5, 6, 7, 8, 9]
n_truncations = [16]
c_truncations = [1]
direction=[2, 1, 0, 3]
# direction = []
hhh.loop_structure(direction = direction, n_truncations = n_truncations, c_truncations = c_truncations)