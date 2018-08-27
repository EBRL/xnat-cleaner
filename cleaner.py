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
    def __init__(self, subject_label, database='CUTTING', xnat=None):
        "Initialize subject and connections to XNAT."
        
        self.subject = subject_label
        self.database = database
        
        # Create XNAT interface if not provided
        if xnat is None:
            xnat = dax.XnatUtils.get_interface()
        self.interface = xnat
        
        # Select XNAT object
        self.xnat_object = xnat.select.project(database).subject(subject_label)
        
        # Populate metadata for subject
        self.get_metadata()
    
    
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


    def match_scan_types(self, overwrite=False):
        "Match scans from self.scan_df to the repository of possible scan renames."

        rename_dict = self.get_scan_rename_dict()
        
        for _, scan in self.scan_df.iterrows():
            scan_tuple = (scan.series_description, scan.scan_type)
            if scan_tuple in rename_dict.keys():
                new_type = rename_dict[scan_tuple]

                # Update the attribute on XNAT, if overwrite is selected
                if overwrite == True:
                    self.interface.select(scan.ID).attrs.set('scan_type', new_type)


    def get_scan_rename_dict(self):
        """Generate a dictionary of (series_description, scan_type) pairs that encode a 
        valid renaming instance. Top-level dicionary is indexed by EBRL project."""

        df = pandas.read_csv('scan_type_renames.csv')

        rename_dict = {}
        for ii, s in df.loc[df.project == self.meta['project']]:
            rename_dict[(s.series_description, s.scan_type)] = s.updated_scan_type

        return rename_dict       
        
        
        
        
def test_xnat_subject(xnat_subject):
    """Run a series of test functions on an instance of XnatSubject. These actions include:
    
    Included functions:
        check_duplicate_scans: Checking for duplicate scans
        check_incomplete_scans: Check if the scan is of type "Incomplete" or "Unusable" in it
        Check if the scan and scan data has a renaming rule in a database
        Check if the scan quality is consistent with expectations (e.g. same amount of frames)
    """
    
    def check_duplicate_scans(xnat_subject):
        "Check for duplicate scan names that are not allowable (i.e. not 'Incomplete')."
        df = xnat_subject.scan_df
        duplicates = df.loc[df.scan_type.duplicated()]
        try: 
            assert duplicates.shape[0] == 0
            print('No duplicate scan types.')
        except:
            print('There are duplicate scans:\n' + duplicates['scan_type'].to_string())
            
    
    def check_incomplete_scans(xnat_subject):
        "Check for scans tagged with 'Incomplete' or 'Unusable'."
        df = xnat_subject.scan_df
        bad_strings = ['inc', 'bad', 'incomplete']

        bad_scans = df.scan_type.apply(lambda x: any(s in x for s in bad_strings))
        try:
            assert bad_scans.sum() == 0
            print('No incomplete or unusable scans.')
        except:
            print('There are incomplete scans:\n' +
                  df.loc[bad_scans==True, 'scan_type'].to_string())

            
    print('Output log for {}:'.format(x.subject))
    check_duplicate_scans(xnat_subject)
    check_incomplete_scans(xnat_subject)