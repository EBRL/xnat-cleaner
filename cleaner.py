import dax
import pandas


class XnatSubject:
    """Extract data from XNAT associated with a single subject. Connects to XNAT using
    user's credentials (set up previously in DAX), then pulls subject information and 
    recommends updates to scan and session information.
    
    Attributes:
        subject: XNAT subject_label (e.g. LD4001_v1)
        meta: metadata dictionary associated with subject
        database: XNAT project (e.g. CUTTING)
        interface: `dax.XnatUtils` interface instance
        sess_df: Pandas DataFrame showing all subject sessions
        scan_df: Pandas DataFrame showing all subject scans

    Methods:
        get_metadata(): Extract session and scan DataFrames.
        match_scan_types(): Checks `scan_type_renames.csv` for suggested name changes.
        update_scan_types(): Applies scan type updates to XNAT scans.       
    """    
    def __init__(self, subject_label, database='CUTTING', xnat=None, 
                 print_summary=False):
        "Initialize subject and connections to XNAT."
        
        self.subject = subject_label
        self.database = database
        
        # Create XNAT interface if not provided
        if xnat is None:
            xnat = dax.XnatUtils.get_interface()
        self.interface = xnat
        
        # Select XNAT object
        self.xnat_object = xnat.select.project(database).subject(subject_label)
        
        # Gather metadata and evaluate subject
        self.get_metadata()
        self.match_scan_types()
        self.run_test_functions()

        # Print summary if requested
        if print_summary == True:
            self.print_summary()

        
    def get_metadata(self):
        "Return information about the subject's sessions and scans."
        
        # Get data on the individual session
        session_data = dax.XnatUtils.list_sessions(self.interface, 
                                                   self.database, 
                                                   self.subject)
        sess_df = pandas.DataFrame(session_data)
        
        # Get data on each individual scan
        scan_data = []
        for ii, sess in sess_df.iterrows():
            scan_data += dax.XnatUtils.list_scans(self.interface, 
                             self.database, self.subject, sess['label'])
        scan_df = pandas.DataFrame(scan_data)
        
        # Throw error if there is more than one session available
        if len(session_data) != 1:
            raise ValueError('This subject has too many sessions in XNAT. Please combine them.')

        self.meta = {'project': self.subject[0:3],
                     'nsessions': len(session_data),
                     'session_date': sess_df['date'].tolist(), 
                     'session_id': sess_df['ID'].tolist(),
                     'session_label': sess_df['label'].tolist(),
                     'subject_id': sess_df['subject_ID'].tolist()
                    }
        self.session_df = sess_df
        self.scan_df = scan_df


    def update_scan_types(self, overwrite=False):
        """
        Performs the entire scan type evaluation process. If overwrite is True,
        this function will update each object on XNAT with the suggested
        scan type rename. If False, it will simply print the suggested renames.
        """
        # loop through each item in the matched scan types and rename
        for scan_id, new_type in self.scan_renames.iteritems():
            s  = self.scan_df.loc[self.scan_df.ID == scan_id].iloc[0]
            obj = (self.interface.select.project('CUTTING')
                       .subject(s.subject_label)
                       .experiment(s.session_label)
                       .scan(scan_id) )
                    
            # Update the attribute on XNAT, if overwrite is selected
            if overwrite == True:
                obj.attrs.set('type', new_type)
                print('Updated {} ({}, {}) to new scan type: {}'.format(scan_id, 
                                      s.series_description, s.scan_type, new_type))
            
            # Otherwise, just print the updated 
            else:
                print('Suggested scan rename: {} ({}, {}) to {}.'.format(scan_id, 
                                      s.series_description, s.scan_type, new_type))

        # If scans updated, refresh the scan metadata and scan_type matches
        if overwrite == True:
            self.get_metadata()
            self.match_scan_types()

                
    def match_scan_types(self):
        """
        Match scans from self.scan_df to the repository of possible scan renames.
        Returns a dictionary of suggested "scan type" renames.
        """
        
        # Initialize dictionary of scan_renames
        rename_dict = self.get_scan_rename_dict()
        self.scan_renames = {}

        for _, scan in self.scan_df.iterrows():
            scan_tuple = (scan.series_description, scan.scan_type)
            if scan_tuple in rename_dict.keys():
                self.scan_renames[scan.ID] = rename_dict[scan_tuple]

                
    def get_scan_rename_dict(self):
        """Generate a dictionary of (series_description, scan_type) pairs that encode a 
        valid renaming instance. Top-level dicionary is indexed by EBRL project."""

        df = pandas.read_csv('scan_type_renames.csv')

        rename_dict = {}
        for ii, s in df.loc[df.project == self.meta['project']].iterrows():
            rename_dict[(s.series_description, s.scan_type)] = s.updated_scan_type

        return rename_dict       
        
        
    def run_test_functions(self):
        """Run a series of test functions on an instance of XnatSubject. These actions include:
        
        Included functions:
            check_duplicate_scans: Checking for duplicate scans
            check_unusable_scans: Check if the scan is of type "Incomplete" or "Unusable" in it
            Check if the scan and scan data has a renaming rule in a database
            Check if the scan quality is consistent with expectations (e.g. same amount of frames)
        """

        self.log = {}         
        self.check_duplicate_scans()
        self.check_unusable_scans()
    
    
    def check_duplicate_scans(self):
        "Check for duplicate scan names that are not allowable (i.e. not 'Incomplete')."
        duplicates = self.scan_df.loc[self.scan_df.scan_type.duplicated()]

        try: 
            assert duplicates.shape[0] == 0
            self.log['duplicate_scans'] = None
        except AssertionError:
            cols = ['ID', 'subject_label', 'session_label', 'scan_type']
            self.log['duplicate_scans'] = duplicates[cols].to_records()

        
    def check_unusable_scans(self):
        "Check for scans tagged with 'Incomplete' or 'Unusable'."
        
        # Select rows from scan_df with unusable scans
        def evaluate_type(scan_type):
            if scan_type == 'Unusable':
                return False         
            
            bad_strings = ['inc', 'bad', 'incomplete', 'unusable']
            if any(s in scan_type.lower() for s in bad_strings):
                return True
            else:
                return False
        
        unusables = self.scan_df.loc[self.scan_df.scan_type.apply(evaluate_type)]

        try:
            assert unusables.shape[0] == 0
            self.log['unusable_scans'] = None
        except AssertionError:
            cols = ['ID', 'subject_label', 'session_label', 'scan_type']
            self.log['unusable_scans'] = unusables[cols].to_records()


    def update_unusable_scans(self, overwrite = False):
        "Rename scans tagged as Unusable/Incomplete."
        
        # Select unusable scans and exit if none
        unusables = self.log['unusable_scans']        
        if unusables is None:
            print('No unusable scans to rename.')
            return
        
        # Loop through scans and update if requested
        for scan in unusables:
            obj = (self.interface.select.project('CUTTING')
                       .subject(scan['subject_label'])
                       .experiment(scan['session_label'])
                       .scan(scan['ID']) )
                    
            # Update the attribute on XNAT, if overwrite is selected
            if overwrite == True:
                obj.attrs.set('type', 'Unusable')
                print('Updated {} ({}) to Unusable'.format(scan['ID'], scan['scan_type']))
            
            # Otherwise, just print the updated 
            else:
                print('Suggested scan rename: {} ({}) to Unusable.'
                         .format(scan['ID'], scan['scan_type']) )

        # Refresh the scan metadata and scan_type matches
        if overwrite == True:
            self.get_metadata()
            self.check_unusable_scans()

            
    def print_summary(self):
        'Print a summary of scan data, proposed changes, and erroneous scans.'
        
        # Print subject information
        print('Subject ID: {}'.format(self.subject))
        print('Project: {}'.format(self.meta['project']))
        print('Session(s): {}'.format(','.join(self.meta['session_label'])))
        print('Session date(s): {}'.format(','.join(self.meta['session_date'])))
               
        # Print the proposed scan renames
        self.update_scan_types(overwrite=False)
        
        # Print any duplicate scans
        try:
            d = self.log['duplicate_scans']
            s = '\n\t'.join('{}, {}'.format(str(a), str(b)) for a, b 
                             in d[['ID', 'scan_type']].tolist())
            print('Duplicate scans:\n\t{}'.format(s))
        except:
            print('Duplicate scans: None')
            
        # Print any Unusable scans
        try:
            d = self.log['unusable_scans']
            s = '\n\t'.join('{}, {}'.format(str(a), str(b)) for a, b 
                             in d[['ID', 'scan_type']].tolist())
            print('Unflagged unusable scans:\n\t{}'.format(s))
        except:
            print('Unflagged unusable scans: None')