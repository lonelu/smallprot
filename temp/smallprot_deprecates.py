    ### DEPRECATED FUNCTIONS FOR GENERATING SSEs (The original build_protein from Rina.)
    
    def build_protein_deprecate(self):
        """Iteratively generate a protein using MASTER and Qbits."""
        self._generate_recursive(self.para.num_iter)
        print('output pdbs :')
        print('\n'.join(self.output_pdbs))

    def _generate_recursive(self, recursion_order):
        print('Adding a qbit rep.')
        # search for a contiguous secondary structural element to add
        outdir = os.path.dirname(self.pdbs[-1])
        outfile = outdir + '/stdout'
        print('Querying MASTER')
        query.master_query(self.pdbs[-1], self.targetList, self.para.rmsdCut, 
            topN=None, outfile=outfile, clobber=False)
        print('Searching with Qbits')
        if not os.path.exists(outdir + '/qbit_reps/'):
            try:
                # ensure the second SSE is antiparallel to the first
                query_exists = int(bool(len(self.query_sse_list)))
                first_recursion = (recursion_order == self.para.num_iter - query_exists)
                query.qbits_search(self.pdbs[-1], self.exclusion_pdbs[-1], 
                                   self.chains_dict, outdir, 
                                   self.para.qbits_window, self.para.qbits_rmsd, 
                                   top=10, sec_struct=self.para.secstruct,
                                   antiparallel=first_recursion,
                                   min_nbrs=self.para.min_nbrs, contiguous=True)
            except:
                pass
        if os.path.exists(outdir + '/qbit_reps/'):
            qreps = [outdir + '/qbit_reps/' + pdb_path for pdb_path in os.listdir(outdir + '/qbit_reps/')]
            # iterate over qbit reps to attempt adding more structure to each 
            # until a suitable small protein is found
            print('Testing Qbit reps')
            for i, qrep in enumerate(qreps):
                self._add_qbit_rep(qrep, i, recursion_order, outdir)

    def _add_qbit_rep(self, qrep, i, recursion_order, outdir):
        # determine permissible sets of seed SSEs for Qbits searches
        seed_sse_lists = self._prepare_seed_sse_lists(qrep)
        # iterate over permissible sets of seed SSEs to add more Qbit reps
        for j, seed_sse_list in enumerate(seed_sse_lists):
            _workdir = '{}/{}'.format(outdir, str(i) + string.ascii_lowercase[j])
            if not os.path.exists(_workdir):
                os.mkdir(_workdir)
            _seed_pdb = _workdir + '/seed.pdb'
            pdbutils.merge_pdbs(seed_sse_list, _seed_pdb, min_nbrs=self.para.min_nbrs)
            self.full_sse_list.append(qrep)
            print('SSE List:')
            print('\n'.join(self.full_sse_list))
            # compute the number of satisfied N- and C-termini
            if len(self.full_sse_list) > 2:
                _full_pdb = _workdir + '/full.pdb'
                pdbutils.merge_pdbs(self.full_sse_list, _full_pdb, min_nbrs=self.para.min_nbrs)
                sat = pdbutils.satisfied_termini(_full_pdb, self.para.max_nc_dist)
                self.pdbs.append(_full_pdb)
            else:
                sat = pdbutils.satisfied_termini(_seed_pdb, self.para.max_nc_dist)
                self.pdbs.append(_seed_pdb)
            n_sat = np.sum(sat)
            if self.para.num_iter - recursion_order - 1 > n_sat:
                # if it is impossible to satisfy all N- or C- termini within 
                # the remaining number of iterations, exit the branch early
                self.pdbs = self.pdbs[:-1]
                self.full_sse_list = self.full_sse_list[:-1]
                continue
            # if recursion_order is not 1, continue adding qbit reps 
            if recursion_order > 1:
                _exclusion_pdb = _workdir + '/exclusion.pdb'
                pdbutils.merge_pdbs([self.exclusion_pdbs[-1], qrep], _exclusion_pdb, min_nbrs=self.para.min_nbrs)
                self.exclusion_pdbs.append(_exclusion_pdb)
                self._generate_recursive(recursion_order - 1)
            # if recursion order is 1 and there are enough N/C termini 
            # satisfied, try building loops
            elif n_sat >= self.para.num_iter:
                try_loopgen = False
                n_chains = len(sat)
                for p in permutations(range(n_chains)):
                    if np.all([sat[p[k], p[k+1]] for k in range(n_chains - 1)]):
                        try_loopgen = True
                # check to make sure self.pdbs[-1] hasn't been looped before
                if try_loopgen:
                    with open(self.pdbs[-1], 'r') as f0:
                        f0_read = f0.read()
                        for pdb in self.looped_pdbs:
                            with open(pdb, 'r') as f1:
                                if f0_read == f1.read():
                                    try_loopgen = False
                # if necessary, ensure the compactness criterion is met
                if self.para.screen_compactness:
                    compactness = pdbutils.calc_compactness(self.pdbs[-1])
                    try_loopgen = try_loopgen and (compactness > 0.1)
                if try_loopgen:
                    self.looped_pdbs.append(self.pdbs[-1])
                    self._generate_loops(sat, _workdir, self.loop_range)
            # if unsuccessful, remove the PDB from the running lists
            self.pdbs = self.pdbs[:-1]
            if len(self.exclusion_pdbs) == len(self.pdbs) + 1:
                self.exclusion_pdbs = self.exclusion_pdbs[:-1]
            self.full_sse_list = self.full_sse_list[:-1]
            # do not iterate over other SSE lists if recursion is complete
            if recursion_order == 1:
                break

    def _prepare_seed_sse_lists(self, qrep):
        # if using an external query structure, include it in the Qbits 
        # search until the protein under construction has at least two SSEs
        if len(self.full_sse_list) < 2:
            all_reps = self.query_sse_list + self.full_sse_list + [qrep]
        else:
            all_reps = self.full_sse_list + [qrep]
        if len(all_reps) < 3:
            seed_sse_lists = [all_reps]
        else:
            # extract atomic coordinates of each SSE
            seed_sse_lists = []
            qrep_xyz = []
            qrep_natoms = [0]
            for j, pair_qrep in enumerate(all_reps):
                title = 'struct{}'.format(str(j))
                this_struct = pdbutils.get_struct(title, pair_qrep, self.para.min_nbrs)
                atoms = this_struct.get_atoms()
                qrep_xyz.append(np.array([atom.get_coord() for atom in atoms]))
                qrep_natoms.append(qrep_natoms[-1] + len(qrep_xyz[-1]))
            qrep_xyz = np.vstack(qrep_xyz)
            # compute minimum interatomic distance between SSE pairs
            dists = cdist(qrep_xyz, qrep_xyz)
            n_reps = len(all_reps)
            for j in range(0, n_reps - 1):
                for k in range(j + 1, n_reps):
                    min_dist = np.min(dists[qrep_natoms[j]:qrep_natoms[j+1], qrep_natoms[k]:qrep_natoms[k+1]])
                    # add pairs of SSEs if they are adjacent in space
                    if min_dist < 5.:
                        seed_sse_lists.append([all_reps[j], all_reps[k]])
        return seed_sse_lists

    ### DEPRECATED FUNCTIONS FOR GENERATING LOOPS

    def loop_seed_structure(self, n_truncations=[], c_truncations=[], chain_key_res=[]):       
        """Treat the seed PDB as a complete structure and generate loops.

        Parameters
        ----------
        n_truncations : list
           List of integer counts of residues to truncate from the N-terminus 
           of each chain in the seed structure prior to loop generation.
        c_truncations : list
           List of integer counts of residues to truncate from the C-terminus 
           of each chain in the seed structure prior to loop generation.
        chain_key_res : list
           List of lists, one for each chain in the seed structure, denoting 
           the indices (counted up from 0 at the N-terminus of each chain, 
           regardless of the residue indices in the PDB file) of residues to 
           be retained in steric clash calculations.
        """
        # ensure a seed structure was provided to the class constructor
        if len(self.full_sse_list) == 0:
            raise AssertionError('seed_pdb not provided to constructor.')
        if len(self.pdbs) > 1:
            raise AssertionError('build_protein() has already been run.')
        # compute the number of satisfied N- and C-termini
        sat = pdbutils.satisfied_termini(self.pdbs[0], self.para.max_nc_dist)
        # set n_truncations and c_truncations for loop generation
        # self.n_truncations = n_truncations
        # self.c_truncations = c_truncations
        self.chain_key_res = chain_key_res
        # generate loops
        _full_sse_list = self.full_sse_list.copy()
        self._generate_loops(_full_sse_list, sat, self.workdir, self.loop_range) 
        print('output pdbs :')
        print('\n'.join(self.output_pdbs))

    ### FUNCTIONS FOR GENERATING LOOPS

    def _generate_loops(self, _full_sse_list, sat, workdir, loop_range=[3, 20]):
        n_chains = len(sat)
        # find loops for each pair of nearby N- and C-termini
        slice_lengths = self._loop_search_fast(_full_sse_list, sat, workdir, loop_range)
        loop_success = self._get_loop_success(sat, workdir, loop_range)
        outfiles = []
        counter = 0
        for p in permutations(range(n_chains)):
            # if loops were built between all successive SSEs in the 
            # permutation of SSE order, continue on to add in the loops
            if np.all([loop_success[p[j], p[j+1]] for j in range(n_chains - 1)]):
                all_centroids, num_clusters, cluster_key_res, no_clusters = self._get_top_clusters(workdir, n_chains, slice_lengths, p, loop_range)
                if no_clusters:
                    continue
                # test whether any selection of loops avoids clashing
                some_outfiles, counter = \
                    self._test_topologies(_full_sse_list, workdir, p, all_centroids, 
                                          cluster_key_res, slice_lengths, 
                                          num_clusters, n_chains, counter)
                outfiles += some_outfiles
        self.output_pdbs += outfiles
    
    def _loop_search(self, _full_sse_list, sat, workdir, loop_range=[3, 20]):
        """The function will be called when the recursion_order == 0 to construct the final small protein."""
        n_chains = len(sat)
        loop_success = np.zeros_like(sat)
        slice_lengths = np.zeros((sat.shape[0], sat.shape[1], 2), dtype=int)
        for j, k in product(range(n_chains), repeat=2):
            # ensure selected SSEs satisfy the distance constraint
            if not sat[j, k] or j == k:
                continue
            print('Generating loops between SSEs {} '
                  'and {}'.format(string.ascii_uppercase[j], 
                                  string.ascii_uppercase[k]))
            loop_workdir = workdir + \
                           '/loops_{}_{}'.format(string.ascii_uppercase[j], 
                                                 string.ascii_uppercase[k])
            if not os.path.exists(loop_workdir):
                os.mkdir(loop_workdir)
            loop_query = loop_workdir + '/loop_query.pdb'
            loop_outfile = loop_workdir + '/stdout'
            # calculate how many residues are required for an overlap region 
            # of length 10 Angstroms between the query SSEs and the loops
            slice_lengths[j, k] = \
                pdbutils.gen_loop_query([_full_sse_list[j], 
                                         _full_sse_list[k]], 
                                        loop_query, min_nbrs=self.para.min_nbrs)
            # find loops with MASTER
            clusters_exist = True
            for l in range(loop_range[0], loop_range[1] + 1):
                subdir = loop_workdir + '/{}'.format(str(l))
                if not os.path.exists(subdir):
                    os.mkdir(subdir)
                    print('Querying MASTER for loops '
                          'of length {}'.format(str(l)))
                    query.master_query_loop(loop_query, self.para.loop_target_list, 
                                            rmsdCut=self.para.rmsdCut, topN=200,
                                            gapLen=l, outdir=subdir, 
                                            outfile=loop_outfile)
                if not os.path.exists(subdir + '/clusters'):
                    clusters_exist = False
            # cluster loops if the clusters do not already exist
            if not clusters_exist:
                cluster_loops.run_cluster(loop_workdir + '/', 
                                          outfile=loop_outfile)
            # determine whether clustering succeeded for any loop length
            for l in range(loop_range[0], loop_range[1] + 1):
                subdir = loop_workdir + '/{}'.format(str(l))
                if len(os.listdir(subdir + '/clusters')) > 0:
                    loop_success[j, k] = 1
        return loop_success, slice_lengths

    def _loop_search_fast(self, _full_sse_list, sat, workdir, loop_range=[3, 20]):
        n_chains = len(sat)
        slice_lengths = np.zeros((sat.shape[0], sat.shape[1], 2), dtype=int)
        for j, k in product(range(n_chains), repeat=2):
            # ensure selected SSEs satisfy the distance constraint
            if not sat[j, k] or j == k:
                continue
            print('Generating loops between SSEs {} ' 'and {}'.format(string.ascii_uppercase[j], string.ascii_uppercase[k]))
            loop_workdir = workdir + '/loops_{}_{}'.format(string.ascii_uppercase[j], string.ascii_uppercase[k])
            if not os.path.exists(loop_workdir):
                os.mkdir(loop_workdir)
            loop_query = loop_workdir + '/loop_query.pdb'
            loop_outfile = loop_workdir + '/stdout'
            # calculate how many residues are required for an overlap region 
            # of length 10 Angstroms between the query SSEs and the loops
            slice_lengths[j, k] = pdbutils.gen_loop_query([_full_sse_list[j], 
                                                          _full_sse_list[k]], 
                                                          loop_query, min_nbrs=self.para.min_nbrs)
            # find loops with MASTER
            # sort PDBs into directories by loop length
            clusters_exist = self._loop_search_query_search(loop_workdir, loop_query, loop_outfile, loop_range)
            # cluster loops if the clusters do not already exist
            if not clusters_exist:
                cluster_loops.run_cluster(loop_workdir + '/', outfile=loop_outfile)
        return slice_lengths

    def _loop_search_query_search(self, loop_workdir, loop_query, loop_outfile, loop_range):
        # find loops with MASTER
        gapLen = str(loop_range[0]) + '-' + str(loop_range[1])
        if not os.path.exists(loop_outfile):
            print('Querying MASTER for loops of length {} to {}.'.format(
                    str(loop_range[0]), str(loop_range[1])))
            query.master_query_loop(loop_query, self.para.loop_target_list, 
                                    rmsdCut=self.para.rmsdCut, topN=200,
                                    gapLen=gapLen, outdir=loop_workdir, 
                                    outfile=loop_outfile)
        clusters_exist = True
        loop_workdir_paths = os.listdir(loop_workdir)
        print('Sorting loop PDBs by loop length.')
        # sort PDBs into directories by loop length
        for path in loop_workdir_paths:
            if '.pdb' in path and 'loop_query' not in path:
                with open(loop_workdir + '/' + path, 'r') as f:
                    res_ids = set([int(line[23:26]) for line in 
                                    f.read().split('\n') if 
                                    line[:4] == 'ATOM'])
                    # subtract query ends from loop length
                    l = len(res_ids) - 14
                l_dir = loop_workdir + '/' + str(l)
                # create a directory for the loop length if necessary
                if str(l) not in loop_workdir_paths:
                    os.mkdir(l_dir)
                    loop_workdir_paths.append(str(l))
                os.rename(loop_workdir + '/' + path, l_dir + '/' + os.path.basename(path))
            elif os.path.basename(path) in [str(n) for n in range(100)]:
                clusters_path = loop_workdir + '/' + path + '/clusters'
                if not os.path.exists(clusters_path):
                    os.mkdir(clusters_path)
                    clusters_exist = False
        return clusters_exist

    def _get_loop_success(self, sat, workdir, loop_range=[3, 20]):
        n_chains = len(sat)
        loop_success = np.zeros_like(sat)
        # determine whether clustering succeeded for any loop length
        for j, k in product(range(n_chains), repeat=2):
            loop_workdir = workdir + '/loops_{}_{}'.format(string.ascii_uppercase[j], string.ascii_uppercase[k])
            for l in range(loop_range[0], loop_range[1] + 1):
                subdir = loop_workdir + '/{}'.format(str(l))
                if os.path.exists(subdir):
                    if len(os.listdir(subdir + '/clusters')) > 0:
                        loop_success[j, k] = 1
        return loop_success

    def _get_top_clusters(self, workdir, n_chains, slice_lengths, p, loop_range=[3, 20]):
        all_centroids = []
        num_clusters = []
        cluster_key_res = []
        no_clusters = False
        if not os.path.exists(workdir + '/loop_centroids'):
            os.mkdir(workdir + '/loop_centroids')
        for j in range(n_chains - 1):          
            loop_workdir = workdir + '/loops_{}_{}'.format(string.ascii_uppercase[p[j]], string.ascii_uppercase[p[j+1]])
            l_centroids = []
            cluster_sizes = []
            l_cluster_key_res = []
            for l in range(loop_range[0], loop_range[1] + 1):
                subdir = loop_workdir + '/{}/clusters/1'.format(str(l))                 
                try:
                    loop_pdbs = os.listdir(subdir)
                except:
                    loop_pdbs = []
                if len(loop_pdbs) > 0:
                    if self.para.lowest_rmsd_loop:
                        l_centroids.append(subdir + '/' + self._lowest_rmsd_loop(loop_workdir + '/match.txt', loop_pdbs))
                    else:
                        l_centroids.append([subdir + '/' + lpdb for lpdb in loop_pdbs if 'centroid' in lpdb][0])                   
                    cluster_sizes.append(len(loop_pdbs))                                                       
                    sl = slice_lengths[p[j], p[j+1]]
                    # find "key positions" along the loop that are 
                    # statistically enriched in one residue, so their  
                    # side chains can be included in clash checks
                    l_cluster_key_res.append(self._key_residues(loop_workdir + '/seq.txt', loop_pdbs, sl))                     
            # sort clusters by size
            if len(cluster_sizes) > 0:
                idxsort = np.argsort(cluster_sizes)[::-1]
                all_centroids.append([l_centroids[idx] for idx in idxsort])
                num_clusters.append(len(cluster_sizes))
                cluster_key_res.append([l_cluster_key_res[idx] for idx in idxsort])
            else:
                no_clusters = True
        return all_centroids, num_clusters, cluster_key_res, no_clusters, summaries
                   
    def _lowest_rmsd_loop(self, matchfile, loop_pdbs):
        with open(matchfile, 'r') as f:
            rmsds = [float([val for val in line.split(' ') if val != ''][0]) 
                     for line in f.read().split('\n') if len(line) > 0]
        loop_rmsds = []
        for loop_pdb in loop_pdbs:
            if 'wgap' in loop_pdb:
                idx = int(loop_pdb.split('_')[-1][4:-7]) - 1
            else:
                idx = int(loop_pdb.split('_')[-1][5:-7]) - 1
            loop_rmsds.append(rmsds[idx])
        return loop_pdbs[np.argmin(loop_rmsds)]

    def _key_residues(self, seqfile, loop_pdbs, slice_lengths):
        with open(seqfile, 'r') as f:
            lines = f.read().split('\n')
        all_seqs = []
        for line in lines:
            if len(line) > 0:
                reslist = []
                for res in line.split(' '):
                    if len(res) == 3 and res[0].isalpha():
                        reslist.append(res)
                    elif len(res) == 4 and res[0] == '[':
                        reslist.append(res[1:])
                    elif len(res) == 4 and res[-1] == ']':
                        reslist.append(res[:-1])
                all_seqs.append(reslist)
        seqs = []
        for loop_pdb in loop_pdbs:
            if 'wgap' in loop_pdb:
                idx = int(loop_pdb.split('_')[-1][4:-7]) - 1
            else:
                idx = int(loop_pdb.split('_')[-1][5:-7]) - 1
            seqs.append(all_seqs[idx])
        seqs = np.array(seqs, dtype=str)
        try:
            modes = mode(seqs, axis=0)
        except:
            return []
        # return which positions have one residue across most cluster members
        idxs = np.argwhere(modes.count > 0.7 * len(seqs)).reshape(-1)
        idx_min = slice_lengths[0]
        idx_max = seqs.shape[1] - slice_lengths[1]
        return [idx for idx in idxs if idx > idx_min and idx < idx_max]

    def _test_topologies(self, _full_sse_list, workdir, permutation, all_centroids, 
                         cluster_key_res, slice_lengths, num_clusters, 
                         n_chains, counter):
        some_outfiles = []
        # iterate through loop structures until one is found without 
        # clashes and (optionally) satisfying a compactness criterion
        pdb_dir = os.path.dirname(self.pdbs[-1])
        pdbutils.split_pdb(self.pdbs[-1], pdb_dir, self.para.min_nbrs, None, 
                           self.n_truncations, self.c_truncations)
        chain_pdbs = [pdb_dir + '/' + path for path 
                      in os.listdir(pdb_dir) if 'chain_' in path]
        chain_pdbs.sort()
        #get all combinations of matches in top clusters from each chain.
        loop_idx_sets = np.array(list(product(*[range(num) for num in num_clusters])))
        loop_idx_sets = loop_idx_sets[np.argsort(loop_idx_sets.sum(axis=1))]
        #forbidden is a list of list of matches for each chain that find clash. No need to check clash of it again.
        forbidden = [[]] * len(all_centroids)
        for idxs in loop_idx_sets:
            skip_idxs = False
            for j in range(len(all_centroids)):
                if idxs[j] in forbidden[j]:
                    skip_idxs = True
            if skip_idxs:
                continue
            centroids_gz = [all_centroids[j][idxs[j]] for j in range(len(all_centroids))]
            filenames, centroids, res_ids_to_keep = self._check_clash(workdir, centroids_gz, forbidden, chain_pdbs, permutation, cluster_key_res, idxs)           
            # ensure enough loops were found and check clashes between them
            if len(centroids) != n_chains - 1 or pdbutils.check_clashes(centroids, res_ids_to_keep):
                [os.remove(filename) for filename in filenames]
                continue
            # permute SSEs and connect with loops
            clashing, outfile_path = self._connect_loops(_full_sse_list, workdir, n_chains, permutation, filenames, centroids, counter, slice_lengths)
            if clashing:
                [os.remove(filename) for filename in filenames]
                continue
            if self.para.screen_compactness:
                compactness = pdbutils.calc_compactness(outfile_path)
                if compactness < 0.138:
                    [os.remove(filename) for filename in filenames]
                    continue
            print('full protein output :', outfile_path)
            #print('pdbs_to_combine :', pdbs_to_combine)
            some_outfiles.append(outfile_path)
            counter += 1
            break
        return some_outfiles, counter
 
    def _check_clash(self, workdir, centroids_gz, forbidden, chain_pdbs, permutation, cluster_key_res, idxs):
        filenames = []
        centroids = []
        res_ids_to_keep = []
        for j, centroid in enumerate(centroids_gz):
            dest_name = workdir + '/loop_centroids/' + os.path.basename(centroid)[:-3]
            if not os.path.exists(dest_name):
                with gzip.open(centroid, 'rb') as f_in:
                    with open(dest_name, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                filenames.append(dest_name)
                # check if loop clashes with exclusion PDB
                # or SSEs it does not connect
                loop_clashes = False
                if self.orig_exclusion is not None:
                    loop_clashes = loop_clashes or \
                        pdbutils.check_clashes([dest_name, self.orig_exclusion])
                unlooped_sses = [chain_pdbs[sse_idx] for sse_idx in permutation 
                                    if sse_idx not in permutation[j:j+2]]
                if len(self.chain_key_res) == len(unlooped_sses):
                    sse_key_res = [self.chain_key_res[p_idx] for p_idx in permutation]
                else:
                    sse_key_res = [[]] * len(unlooped_sses)
                loop_clashes = loop_clashes or \
                    pdbutils.check_clashes([dest_name] + unlooped_sses, [cluster_key_res[j][idxs[j]]] + sse_key_res)
                if loop_clashes or pdbutils.check_gaps(dest_name):
                    # remove loops that clash with SSEs or that have gaps 
                    # from future consideration
                    forbidden[j].append(idxs[j])
                    break
            centroids.append(dest_name)
            res_ids_to_keep.append(cluster_key_res[j][idxs[j]])
        return filenames, centroids, res_ids_to_keep
            
    def _connect_loops(self, _full_sse_list, workdir, n_chains, permutation, filenames, centroids, counter, slice_lengths):
        pdbs_to_combine = [''] * (2 * n_chains - 1)
        pdbs_to_combine[::2] = [_full_sse_list[idx] for idx in permutation]
        pdbs_to_combine[1::2] = centroids
        outfile_path = workdir + '/output_{}.pdb'.format(str(counter))
        filenames.append(outfile_path)
        overlaps = []
        for j in range(n_chains - 1):
            overlaps.append(slice_lengths[permutation[j], permutation[j+1], 0])
            overlaps.append(slice_lengths[permutation[j], permutation[j+1], 1])
        clashing = pdbutils.stitch(pdbs_to_combine, outfile_path, 
                                    overlaps=overlaps, 
                                    min_nbrs=self.para.min_nbrs, 
                                    from_closest=False)
        return clashing, outfile_path
    

