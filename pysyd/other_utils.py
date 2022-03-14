import os
import ast
import glob
import numpy as np
import pandas as pd
from tqdm import tqdm
from itertools import chain
from astropy.io import ascii
import multiprocessing as mp
from astropy.stats import mad_std
from astropy.timeseries import LombScargle as lomb

from pysyd import __file__
from pysyd.plots import set_plot_params
from pysyd.models import *


def get_defaults():
    """
    

    """
    # initiate base class
    args = Constants()
    # Get parameters for all modules
    args = get_parameters(args)
    # Get invidual/specific star info from csv file (if it exists)
#    args = get_csv_info(args)

#    set_plot_params()
    return args


def get_parameters(args):
    """
    

    """
    # Initialize main 'params' dictionary
    args = get_main_params(args)
    # Initialize parameters for the find excess routine
    args = get_excess_params(args)
    # Initialize parameters for the fit background routine
    args = get_background_params(args)
    # Initialize parameters relevant for estimating global parameters
    args = get_global_params(args)
    return args


def get_main_params(args, stars=None, excess=False, background=False, globe=False, verbose=True, show=False, 
                    save=False, kep_corr=False, of_actual=None, of_new=None, overwrite=True):
    """  

    """
    args.todo = os.path.join(os.path.abspath(os.getcwd()), 'info', 'todo.txt')
    args.of_actual, args.of_new, args.kep_corr, args.verbose = of_actual, of_new, kep_corr, verbose
    args.params = dict(
        stars = stars,
        inpdir = os.path.join(os.path.abspath(os.getcwd()), 'data'),
        outdir = os.path.join(os.path.abspath(os.getcwd()), 'results'),
        info = os.path.join(os.path.abspath(os.getcwd()), 'info', 'star_info.csv'),
        show = show,
        save = save,
        overwrite = overwrite,
        excess = excess,
        background = background,
        global = globe,
        verbose = verbose,
    )
    return args


def get_excess_params(args, n_trials=3, step=0.25, binning=0.005, smooth_width=20.0, mode='mean', 
                      lower_ex=1.0, upper_ex=8000., ask=False, results={}):
    """
    
    """
    args.excess = dict(
        step = step,
        binning = binning,
        smooth_width = smooth_width,
        ask = ask,
        n_trials = n_trials,
        lower_ex = lower_ex,
        upper_ex = upper_ex,
        results = results,
    )
    return args


def get_background_params(args, ind_width=20.0, box_filter=1.0, n_rms=20, metric='bic', include=False,
                          mc_iter=1, samples=False, n_laws=None, fix_wn=False, basis='tau_sigma',
                          lower_bg=1.0, upper_bg=8000., results={}):
    """

    """
    args.background = dict(
        ind_width = ind_width,
        box_filter = box_filter,
        n_rms = n_rms,
        n_laws = n_laws,
        fix_wn = fix_wn,
        basis = basis,
        metric = metric,
        include = include,
        functions = get_dict(type='functions'),
        mc_iter = mc_iter,
        samples = samples,
        lower_bg = lower_bg,
        upper_bg = upper_bg,
        results = results,
    )
    return args


def get_global_params(args, sm_par=None, lower_ps=None, upper_ps=None, width=1.0, method='D', smooth_ps=2.5, 
                      threshold=1.0, n_peaks=5, cmap='binary', clip_value=3.0, smooth_ech=None, interp_ech=False, 
                      lower_ech=None, upper_ech=None, nox=50, noy=0, notching=False, results={},):
    """

    """
    args.globe = dict(
        sm_par = sm_par,
        width = width,
        smooth_ps = smooth_ps,
        threshold = threshold,
        n_peaks = n_peaks,
        method = method,
        cmap = cmap,
        clip_value = clip_value,
        smooth_ech = smooth_ech,
        interp_ech = interp_ech,
        nox = nox,
        noy = noy,
        notching = notching,
        results = results,
    )
    return args


def get_csv_info(args, force=False, guess=None):
    """
    
    """
    constants = Constants()
    columns = get_dict(type='columns')['required']
    # Open file if it exists
    if os.path.exists(args.info):
        df = pd.read_csv(args.info)
        stars = [str(each) for each in df.stars.values.tolist()]
        for i, star in enumerate(args.params['stars']):
            args.params[star]['excess'] = args.params['excess']
            args.params[star]['force'] = force
            args.params[star]['guess'] = guess
            if star in stars:
                idx = stars.index(star)
                # Update information from columns
                for column in columns:   
                    if not np.isnan(float(df.loc[idx,column])):
                        args.params[star][column] = float(df.loc[idx, column])
                    else:
                        args.params[star][column] = None
                # Add estimate of numax if the column exists
                if args.params[star]['numax'] is not None:
                    args.params[star]['excess'] = False
                    args.params[star]['dnu'] = 0.22*(args.params[star]['numax']**0.797)
                elif args.params[star]['dnu'] is not None:
                    args.params[star]['force'] = True
                    args.params[star]['guess'] = args.params[star]['dnu']
                # Otherwise estimate using other stellar parameters
                else:
                    if args.params[star]['radius'] is not None and args.params[star]['logg'] is not None:
                        args.params[star]['mass'] = ((((args.params[star]['radius']*constants.r_sun)**(2.0))*10**(args.params[star]['logg'])/constants.G)/constants.m_sun)
                        args.params[star]['numax'] = constants.numax_sun*args.params[star]['mass']*(args.params[star]['radius']**(-2.0))*((args.params[star]['teff']/constants.teff_sun)**(-0.5))
                        args.params[star]['dnu'] = constants.dnu_sun*(args.params[star]['mass']**(0.5))*(args.params[star]['radius']**(-1.5))  
            # if target isn't in csv, still save basic parameters called througout the code
            else:
                for column in columns:
                    args.params[star][column] = None
    # same if the file does not exist
    else:
        for star in args.stars:
            args.params[star]['excess'] = args.params['excess']
            args.params[star]['force'] = False
            for column in columns:
                args.params[star][column] = None
    return args


def load_data(star, args):
    """
    
    Loads both the light curve and power spectrum data in for a given star,
    which will return `False` if unsuccessful and therefore, not run the rest
    of the pipeline.

    Args:
        star : target.Target
            the pySYD pipeline object
        args : argparse.Namespace
            command line arguments

    Returns:
        star : target.Target
            the pySYD pipeline object
        star.lc : bool
            will return `True` if the light curve data was loaded in properly otherwise `False`
        star.ps : bool
            will return `True` if the power spectrum file was successfully loaded otherwise `False`

    """
    if not star.params['cli']:
        star.pickles=[]
    # Now done at beginning to make sure it only does this once per star
    if glob.glob(os.path.join(args.inpdir,'%s*'%str(star.name))) != []:
        if star.verbose:
            print('\n\n------------------------------------------------------')
            print('Target: %s'%str(star.name))
            print('------------------------------------------------------')
        # Load light curve
        args, star, note = load_time_series(args, star)
        if star.verbose:
            print(note)
        # Load power spectrum
        args, star, note = load_power_spectrum(args, star)
        if star.verbose:
            print(note)
    return star


def load_file(path):
    """
    
    Load a light curve or a power spectrum from a basic 2xN txt file
    and stores the data into the `x` (independent variable) and `y`
    (dependent variable) arrays, where N is the length of the series.

    args:
        path : str
            the file path of the data file

    Returns:
        x : numpy.array
            the independent variable i.e. the time or frequency array 
        y : numpy.array
            the dependent variable, in this case either the flux or power array

    """
    f = open(path, "r")
    lines = f.readlines()
    f.close()
    # Set values
    x = np.array([float(line.strip().split()[0]) for line in lines])
    y = np.array([float(line.strip().split()[1]) for line in lines])
    return x, y


def load_time_series(args, star, note=''):
    """
    
    If available, star.lc is set to `True`, the time series data
    is loaded in, and then it calculates the cadence and nyquist 
    freqency. If time series data is not provided, either the
    cadence or nyquist frequency must be provided via CLI

    Args:
        star : target.Target
            the pySYD pipeline object
        args : argparse.Namespace
            command line arguments
        args.cadence : int
            cadence of time series data (if known but data is not available)
        args.nyquist : float
            nyquist frequency of the provided power spectrum
        note : str
            optional suppressed verbose output

    Returns:
        star : target.Target
            the pySYD pipeline object
        star.lc : bool
            will return `True` if the light curve data was loaded in properly otherwise `False`
        star.time : numpy.array
            time array in days
        star.flux : numpy.array
            relative or normalized flux array

    """
    star.lc = False
    star.nyquist = None
    # Try loading the light curve
    if os.path.exists(os.path.join(args.inpdir, '%s_LC.txt'%star.name)):
        star.lc = True
        star.time, star.flux = load_file(os.path.join(args.inpdir, '%s_LC.txt'%star.name))
        star.time -= min(star.time)
        star.cadence = int(round(np.nanmedian(np.diff(star.time)*24.0*60.0*60.0),0))
        star.nyquist = 10**6./(2.0*star.cadence)
        star.baseline = (max(star.time)-min(star.time))*24.*60.*60.
        star.tau_upper = star.baseline/2.
        note += '# LIGHT CURVE: %d lines of data read\n# Time series cadence: %d seconds'%(len(star.time),star.cadence)

    return args, star, note


def load_power_spectrum(args, star, note='', long=10**6):
    """

    """
    star.ps = False
    # Try loading the power spectrum
    if not os.path.exists(os.path.join(args.inpdir, '%s_PS.txt'%star.name)):
        note += '# ERROR: %s/%s_PS.txt not found\n'%(args.inpdir, star.name)
    else:
        star.ps = True
        star.frequency, star.power = load_file(os.path.join(args.inpdir, '%s_PS.txt'%star.name))
        note += '# POWER SPECTRUM: %d lines of data read\n'%len(star.frequency)
        if len(star.frequency) >= long:
            note += '# WARNING: PS is large and will slow down the software'
        star.resolution = star.frequency[1]-star.frequency[0]
        if args.kep_corr:
            note += '# **using Kepler artefact correction**\n'
            star = remove_artefact(star)
        if star.params[star.name]['ech_mask'] is not None:
            note += '# **whitening the PS to remove mixed modes**\n'
            star = whiten_mixed(star)
        args, star, note = check_input_data(args, star, note)
    
    return args, star, note


def set_seed(star, lower=1, upper=10**7, size=1):
    """
    
    For Kepler targets that require a correction via CLI (--kc), a random seed is generated
    from U~[1,10^7] and stored in stars_info.csv for reproducible results in later runs.

    Args:
        star : target.Target
            the pySYD pipeline object
        lower : int 
            lower limit for random seed value (default=`1`)
        upper : int
            upper limit for random seed value (default=`10**7`)
        size : int
            number of seed values returned (default=`1`)

    Returns:
        star : target.Target
            the pySYD pipeline object
        
    """

    seed = list(np.random.randint(lower,high=upper,size=size))
    df = pd.read_csv(star.params['info'])
    stars = [str(each) for each in df.stars.values.tolist()]
    idx = stars.index(star.name)
    df.loc[idx,'seed'] = int(seed[0])
    star.params[star.name]['seed'] = seed[0]
    df.to_csv(star.params['info'],index=False)
    return star


def remove_artefact(star, lcp=1.0/(29.4244*60*1e-6), lf_lower=[240.0,500.0], lf_upper=[380.0,530.0], 
                    hf_lower = [4530.0,5011.0,5097.0,5575.0,7020.0,7440.0,7864.0],
                    hf_upper = [4534.0,5020.0,5099.0,5585.0,7030.0,7450.0,7867.0],):
    """

    """

    if star.params[star.name]['seed'] is None:
        star = set_seed(star)
    # LC period in Msec -> 1/LC ~muHz
    artefact = (1.0+np.arange(14))*lcp
    # Estimate white noise
    white = np.mean(star.power[(star.frequency >= max(star.frequency)-100.0)&(star.frequency <= max(star.frequency)-50.0)])

    np.random.seed(int(star.params[star.name]['seed']))
    # Routine 1: remove 1/LC artefacts by subtracting +/- 5 muHz given each artefact
    for i in range(len(artefact)):
        if artefact[i] < np.max(star.frequency):
            mask = np.ma.getmask(np.ma.masked_inside(star.frequency, artefact[i]-5.0*star.resolution, artefact[i]+5.0*star.resolution))
            if np.sum(mask) != 0:
                star.power[mask] = white*np.random.chisquare(2,np.sum(mask))/2.0

    np.random.seed(int(star.params[star.name]['seed']))
    # Routine 2: fix high frequency artefacts
    for lower, upper in zip(hf_lower, hf_upper):
        if lower < np.max(star.frequency):
            mask = np.ma.getmask(np.ma.masked_inside(star.frequency, lower, upper))
            if np.sum(mask) != 0:
                star.power[mask] = white*np.random.chisquare(2,np.sum(mask))/2.0

    np.random.seed(int(star.params[star.name]['seed']))
    # Routine 3: remove wider, low frequency artefacts 
    for lower, upper in zip(lf_lower, lf_upper):
        low = np.ma.getmask(np.ma.masked_outside(star.frequency, lower-20., lower))
        upp = np.ma.getmask(np.ma.masked_outside(star.frequency, upper, upper+20.))
        # Coeffs for linear fit
        m, b = np.polyfit(star.frequency[~(low*upp)], star.power[~(low*upp)], 1)
        mask = np.ma.getmask(np.ma.masked_inside(star.frequency, lower, upper))
        # Fill artefact frequencies with noise
        star.power[mask] = ((star.frequency[mask]*m)+b)*(np.random.chisquare(2, np.sum(mask))/2.0)

    return star


def whiten_mixed(star, notching=False):
    """
    Remove mixed modes
    
    Module to help reduce the effects of mixed modes random white noise in place of ell=1 for subgiants with mixed modes to better
    constrain the characteristic frequency spacing.

    Parameters
    ----------
    star : target.Target
        pySYD pipeline target
    star.frequency : np.ndarray
        the frequency of the power spectrum
    star.power : np.ndarray
        the power spectrum

    """
    if star.params[star.name]['seed'] is None:
        star = set_seed(star)
    # Estimate white noise
    if not star.globe['notching']:
        white = np.mean(star.power[(star.frequency >= max(star.frequency)-100.0)&(star.frequency <= max(star.frequency)-50.0)])
    else:
        white = min(star.power[(star.frequency >= max(star.frequency)-100.0)&(star.frequency <= max(star.frequency)-50.0)])
    # Take the provided dnu and "fold" the power spectrum
    folded_freq = np.copy(star.frequency)%star.params[star.name]['guess']
    mask = np.ma.getmask(np.ma.masked_inside(folded_freq, star.params[star.name]['ech_mask'][0], star.params[star.name]['ech_mask'][1]))
    np.random.seed(int(star.params[star.name]['seed']))
    # Makes sure the mask is not empty
    if np.sum(mask) != 0:
        if star.globe['notching']:
            star.power[mask] = white
        else:
            star.power[mask] = white*np.random.chisquare(2,np.sum(mask))/2.0
    # Typically if dnu is provided, it will assume you want to "force" that value
    # so we need to adjust this back
    star.params[star.name]['force'] = False
    star.params[star.name]['guess'] = None
    return star


def check_input_data(args, star, note):
    """

    """
    if star.lc:
        args.of_actual = int(round((1./((max(star.time)-min(star.time))*0.0864))/(star.frequency[1]-star.frequency[0])))
        star.freq_cs = np.array(star.frequency[args.of_actual-1::args.of_actual])
        star.pow_cs = np.array(star.power[args.of_actual-1::args.of_actual])
        if args.of_new is not None:
            note += '# Computing new PS using oversampling of %d\n'%args.of_new
            freq_os, pow_os = lomb(star.time, star.flux).autopower(method='fast', samples_per_peak=args.of_new, maximum_frequency=star.nyquist)
            star.freq_os = freq_os*(10.**6/(24.*60.*60.))
            star.pow_os = 4.*pow_os*np.var(star.flux*1e6)/(np.sum(pow_os)*(star.freq_os[1]-star.freq_os[0]))
        else:
            star.freq_os, star.pow_os = np.copy(star.frequency), np.copy(star.power)
    else:
        if args.of_actual is not None:
            star.freq_cs = np.array(star.frequency[args.of_actual-1::args.of_actual])
            star.pow_cs = np.array(star.power[args.of_actual-1::args.of_actual])
            star.freq_os, star.pow_os = np.copy(star.frequency), np.copy(star.power)                    
        else:
            star.freq_cs, star.pow_cs = np.copy(star.frequency), np.copy(star.power)
            star.freq_os, star.pow_os = np.copy(star.frequency), np.copy(star.power)
            note += '# WARNING: using input PS with no additional information\n'
            if args.mc_iter > 1:
                note += '# **uncertainties may not be reliable unless using a critically-sampled PS**'
        star.baseline = 1./((star.freq_cs[1]-star.freq_cs[0])*10**-6.)
        star.tau_upper = star.baseline/2.
    if args.of_actual is not None and args.of_actual != 1:
        note += '# PS is oversampled by a factor of %d\n'%args.of_actual
    else:
        note += '# PS is critically-sampled\n'
    note += '# PS resolution: %.6f muHz'%(star.freq_cs[1]-star.freq_cs[0])
    return args, star, note


def get_estimates(star, max_trials=6):
    """
    
    Parameters used with the first module, which is an automated method to identify
    power excess due to solar-like oscillations.

    Args:
        star : target.Target
            pySYD target object
	max_trials : int, optional
	    the number of "guesses" or trials to perform to estimate numax

    Returns:
        star : target.Target
            updated pySYD target object


    """
    # If running the first module, mask out any unwanted frequency regions
    star.frequency, star.power = np.copy(star.freq_os), np.copy(star.pow_os)
    star.resolution = star.frequency[1]-star.frequency[0]
    # mask out any unwanted frequencies
    if star.params[star.name]['lower_ex'] is not None:
        lower = star.params[star.name]['lower_ex']
    else:
        if star.excess['lower_ex'] is not None:
            lower = star.excess['lower_ex']
        else:
            lower = min(star.frequency)
    if star.params[star.name]['upper_ex'] is not None:
        upper = star.params[star.name]['upper_ex']
    else:
        if star.excess['upper_ex'] is not None:
            upper = star.excess['upper_ex']
        else:
            upper = max(star.frequency)
        if star.nyquist is not None and star.nyquist < upper:
            upper = star.nyquist
    star.freq = star.frequency[(star.frequency >= lower)&(star.frequency <= upper)]
    star.pow = star.power[(star.frequency >= lower)&(star.frequency <= upper)]
    if star.excess['n_trials'] > max_trials:
        star.excess['n_trials'] = max_trials
    if (star.params[star.name]['numax'] is not None and star.params[star.name]['numax'] <= 500.) or (star.nyquist is not None and star.nyquist <= 300.):
        star.boxes = np.logspace(np.log10(0.5), np.log10(25.), star.excess['n_trials'])
    else:
        star.boxes = np.logspace(np.log10(50.), np.log10(500.), star.excess['n_trials'])
    return star


def check_numax(star):
    """
    
    Checks if there is a starting value for numax

    Returns:
        bool
            will return `True` if there is prior value for numax otherwise `False`.

    """
    # THIS MUST BE FIXED TOO
    # Check if numax was provided as input
    if star.params[star.name]['numax'] is None:
        # If not, checks if findex was run
        if not star.params['overwrite']:
            dir = os.path.join(star.params[star.name]['path'],'estimates*')
        else:
            dir = os.path.join(star.params[star.name]['path'],'estimates.csv')
        if glob.glob(dir) != []:
            if not star.params['overwrite']:
                list_of_files = glob.glob(os.path.join(star.params[star.name]['path'],'estimates*'))
                file = max(list_of_files, key=os.path.getctime)
            else:
                file = os.path.join(star.params[star.name]['path'],'estimates.csv')
            df = pd.read_csv(file)
            for col in ['numax', 'dnu', 'snr']:
                star.params[star.name][col] = df.loc[0, col]
        # No estimate for numax provided and/or determined
        else:
            return False
    return True


def get_initial(star, lower_bg=1.0):
    """
    
    Gets initial guesses for granulation components (i.e. timescales and amplitudes) using
    solar scaling relations. This resets the power spectrum and has its own independent
    filter (i.e. [lower,upper] mask) to use for this subroutine.

    Args:
        star : target.Target
            pySYD target object
        star.oversample : bool
            if `True`, it will use an oversampled power spectrum for the first iteration or 'step'
        minimum_freq : float
            minimum frequency to use for the power spectrum if `None` is provided (via info/star_info.csv). Default = `10.0` muHz. Please note: this is typically sufficient for most stars but may affect evolved stars!
        maximum_freq : float
            maximum frequency to use for the power spectrum if `None` is provided (via info/star_info.csv). Default = `5000.0` muHz.

    Returns:
        star : target.Target
            updated pySYD target object


    """
    star.frequency, star.power = np.copy(star.freq_os), np.copy(star.pow_os)
    star.resolution = star.frequency[1]-star.frequency[0]

    if star.params[star.name]['lower_bg'] is not None:
        lower = star.params[star.name]['lower_bg']
    else:
        lower = lower_bg
    if star.params[star.name]['upper_bg'] is not None:
        upper = star.params[star.name]['upper_bg']
    else:
        upper = max(star.frequency)
        if star.nyquist is not None and star.nyquist < upper:
            upper = star.nyquist
    star.params[star.name]['bg_mask']=[lower,upper]

    # Mask power spectrum for fitbg module
    mask = np.ma.getmask(np.ma.masked_inside(star.frequency, star.params[star.name]['bg_mask'][0], star.params[star.name]['bg_mask'][1]))
    star.frequency, star.power = np.copy(star.frequency[mask]), np.copy(star.power[mask])
    star.random_pow = np.copy(star.power)
    # Get other relevant initial conditions
    star.i = 0
    if star.params['background']:
        star.background['results'][star.name] = {}
    if star.params['global']:
        star.globe['results'][star.name] = {}
        star.globe['results'][star.name] = {'numax_smooth':[],'A_smooth':[],'numax_gauss':[],'A_gauss':[],'FWHM':[],'dnu':[]}
    if star.params['testing']:
        star.test='----------------------------------------------------\n\nTESTING INFORMATION:\n'
    # Use scaling relations from sun to get starting points
    star = solar_scaling(star)
    return star


def solar_scaling(star, scaling='tau_sun_single', max_laws=3, times=1.5, scale=1.0):
    """
    Solar scaling relation
    
    Uses scaling relations from the Sun to:
    1) estimate the width of the region of oscillations using numax
    2) guess starting values for granulation timescales

    Args:
        star : target.Target
	    pySYD target object
	scaling : str
	    which scaling relation to use
        max_laws : int
            the maximum number of resolvable Harvey-like components
	times : float
	    
    Returns:
        star : target.Target
            updated pySYD target object

    """
    constants = Constants()
    # Checks if there's an estimate for numax
    # Use "excess" for different meaning now - i.e. is there a power excess
    # as in, if it's (True by default, it will search for it but if it's False, it's saying there isn't any)
    if check_numax(star):
        star.exp_numax = star.params[star.name]['numax']
        # Use scaling relations to estimate width of oscillation region to mask out of the background fit
        width = constants.width_sun*(star.exp_numax/constants.numax_sun)
        maxpower = [star.exp_numax-(width*star.globe['width']), star.exp_numax+(width*star.globe['width'])]
        if star.params[star.name]['lower_ps'] is not None:
            maxpower[0] = star.params[star.name]['lower_ps']
        if star.params[star.name]['upper_ps'] is not None:
            maxpower[1] = star.params[star.name]['upper_ps']
        star.params[star.name]['ps_mask'] = [maxpower[0],maxpower[1]]
        # Use scaling relation for granulation timescales from the sun to get starting points
        scale = constants.numax_sun/star.exp_numax
    # If not, uses entire power spectrum
    else:
        maxpower = [np.median(star.frequency), np.median(star.frequency)]
        if star.params[star.name]['lower_ps'] is not None:
            maxpower[0] = star.params[star.name]['lower_ps']
        if star.params[star.name]['upper_ps'] is not None:
            maxpower[1] = star.params[star.name]['upper_ps']
        star.params[star.name]['ps_mask'] = [maxpower[0],maxpower[1]]
    # Estimate granulation time scales
    if scaling == 'tau_sun_single':
        taus = np.array(constants.tau_sun_single)*scale
    else:
        taus = np.array(constants.tau_sun)*scale
    taus = taus[taus <= star.baseline]
    b = taus*10**-6.
    mnu = (1.0/taus)*10**5.
    star.b = b[mnu >= min(star.frequency)]
    star.mnu = mnu[mnu >= min(star.frequency)]
    if len(star.mnu)==0:
        star.b = b[mnu >= 10.] 
        star.mnu = mnu[mnu >= 10.]
    elif len(star.mnu) > max_laws:
        star.b = b[mnu >= min(star.frequency)][-max_laws:]
        star.mnu = mnu[mnu >= min(star.frequency)][-max_laws:]
    else:
        pass
    # Save copies for plotting after the analysis
    star.nlaws = len(star.mnu)
    star.nlaws_orig = len(star.mnu)
    star.mnu_orig = np.copy(star.mnu)
    star.b_orig = np.copy(star.b)
    return star


#####################################################################
# Save information
#

def save_file(star, formats=[">15.8f", ">18.10e"]):
    """
    Saves background-subtracted power spectrum
    
    After determining the best-fit stellar background model, this module
    saved the background-subtracted power spectrum

    Args:
        star : target.Target
            the pySYD pipeline target
        formats : List[str]
            2x1 list of formats to save arrays as
        star.params[star.name]['path'] : str
            path to save the background-corrected power spectrum
        star.frequency : ndarray
            frequency array
        star.bg_corr_sub : ndarray
            background-subtracted power spectrum


    """
    f_name = os.path.join(star.params[star.name]['path'],'bgcorr_ps.txt')
    if not star.params['overwrite']:
        f_name = get_next(star,'bgcorr_ps.txt')
    with open(f_name, "w") as f:
        for x, y in zip(star.frequency, star.bg_corr):
            values = [x, y]
            text = '{:{}}'*len(values) + '\n'
            fmt = sum(zip(values, formats), ())
            f.write(text.format(*fmt))
    f.close()
    if star.verbose:
        print(' **background-corrected PS saved**')


def save_estimates(star):
    """
    
    Saves the estimate for numax (from first module)

    Args:
        star : target.Target
            pipeline target with the results of the `find_excess` routine


    """
    best = star.excess['results'][star.name]['best']
    variables = ['star', 'numax', 'dnu', 'snr']
    results = [star.name, star.excess['results'][star.name][best]['numax'], star.excess['results'][star.name][best]['dnu'], star.excess['results'][star.name][best]['snr']]
    save_path = os.path.join(star.params[star.name]['path'],'estimates.csv')
    if not star.params['overwrite']:
        save_path = get_next(star,'estimates.csv')
    ascii.write(np.array(results), save_path, names=variables, delimiter=',', overwrite=True)


def save_results(star):
    """
    
    Saves the derived global asteroseismic parameters (from the main module)

    Args:
        star : target.Target
            pipeline target with the results of the `fit_background` routine


    """
    results={}
    if star.params['background']:
        results.update(star.background['results'][star.name])
    if star.params['global']:
        results.update(star.globe['results'][star.name])
    df = pd.DataFrame(results)
    star.df = df.copy()
    new_df = pd.DataFrame(columns=['parameter', 'value', 'uncertainty'])
    for c, col in enumerate(df.columns.values.tolist()):
        new_df.loc[c, 'parameter'] = col
        new_df.loc[c, 'value'] = df.loc[0,col]
        if star.background['mc_iter'] > 1:
            new_df.loc[c, 'uncertainty'] = mad_std(df[col].values)
        else:
            new_df.loc[c, 'uncertainty'] = '--'
    if not star.params['overwrite']:
        new_df.to_csv(get_next(star,'global.csv'), index=False)
    else:
        new_df.to_csv(os.path.join(star.params[star.name]['path'],'global.csv'), index=False)
    if star.background['samples']:
        df.to_csv(os.path.join(star.params[star.name]['path'],'samples.csv'), index=False)


#####################################################################
# Optional verbose output function
#

def verbose_output(star):
    """
    Verbose output

    Prints the results from the global asteroseismic fit (if args.verbose is `True`)


    """
    note=''
    params = get_dict()
    if not star.params['overwrite']:
        list_of_files = glob.glob(os.path.join(star.params[star.name]['path'],'global*'))
        file = max(list_of_files, key=os.path.getctime)
    else:
        file = os.path.join(star.params[star.name]['path'],'global.csv')
    df = pd.read_csv(file)
    if star.background['mc_iter'] > 1:
        note+='\nOutput parameters:'
        line='\n%s: %.2f +/- %.2f %s'
        for idx in df.index.values.tolist():
            note+=line%(df.loc[idx,'parameter'],df.loc[idx,'value'],df.loc[idx,'uncertainty'],params[df.loc[idx,'parameter']]['unit'])
    else:
        note+='------------------------------------------------------\nOutput parameters:'
        line='\n%s: %.2f %s'
        for idx in df.index.values.tolist():
            note+=line%(df.loc[idx,'parameter'],df.loc[idx,'value'],params[df.loc[idx,'parameter']]['unit'])
    note+='\n------------------------------------------------------'
    print(note)


#####################################################################
# Concatenates data for individual stars into a single csv
#

def scrape_output(args):
    """
    Concatenate results
    
    Takes the results from each processed target and concatenates the results into a single csv 
    for each submodule (i.e. excess.csv and background.csv). This is automatically called if pySYD 
    successfully runs for at least one star (count >= 1)
    

    """
    path = os.path.join(args.params['outdir'],'**','')
    # Findex outputs
    files = glob.glob('%s*estimates.csv'%path)
    if files != []:
        df = pd.read_csv(files[0])
        for i in range(1,len(files)):
            df_new = pd.read_csv(files[i])
            df = pd.concat([df, df_new])
        df.to_csv(os.path.join(args.params['outdir'],'estimates.csv'), index=False)

    # Fitbg outputs
    files = glob.glob('%s*global.csv'%path)
    if files != []:
        df = pd.DataFrame(columns=['star'])
        for i, file in enumerate(files):
	           df_new = pd.read_csv(file)
	           df_new.set_index('parameter',inplace=True,drop=False)
	           df.loc[i,'star'] = os.path.split(os.path.split(file)[0])[1]
	           new_header_names=[[i,i+'_err'] for i in df_new.index.values.tolist()]
	           new_header_names=list(chain.from_iterable(new_header_names))          
	           for col in new_header_names:
		              if '_err' in col:
			                 df.loc[i,col]=df_new.loc[col[:-4],'uncertainty']
		              else:
			                 df.loc[i,col]=df_new.loc[col,'value']

        df.fillna('--', inplace=True)
        df.to_csv(os.path.join(args.params['outdir'],'global.csv'), index=False)


#####################################################################
# Read in large python containers (dictionaries) 
#

def get_dict(type='params'):
    """
    Read dictionary
    
    Quick function to read in longer python dictionaries, which is primarily used in
    the utils script (i.e. verbose_output, scrape_output) and in the pipeline script 
    (i.e. setup)

    Args:
        type : str
            which dictionary to read in, choices ~['params','columns']. Default is 'params'.

    Returns:
        result : Dict[str,Dict[,]]
            the loaded, relevant dictionary


    """
    if type == 'functions':
        return {
                0: lambda white_noise : (lambda frequency : harvey_none(frequency, white_noise)),
                1: lambda frequency, white_noise : harvey_none(frequency, white_noise), 
                2: lambda white_noise : (lambda frequency, tau_1, sigma_1 : harvey_one(frequency, tau_1, sigma_1, white_noise)), 
                3: lambda frequency, tau_1, sigma_1, white_noise : harvey_one(frequency, tau_1, sigma_1, white_noise), 
                4: lambda white_noise : (lambda frequency, tau_1, sigma_1, tau_2, sigma_2 : harvey_two(frequency, tau_1, sigma_1, tau_2, sigma_2, white_noise)), 
                5: lambda frequency, tau_1, sigma_1, tau_2, sigma_2, white_noise : harvey_two(frequency, tau_1, sigma_1, tau_2, sigma_2, white_noise),
                6: lambda white_noise : (lambda frequency, tau_1, sigma_1, tau_2, sigma_2, tau_3, sigma_3 : harvey_three(frequency, tau_1, sigma_1, tau_2, sigma_2, tau_3, sigma_3, white_noise)),
                7: lambda frequency, tau_1, sigma_1, tau_2, sigma_2, tau_3, sigma_3, white_noise : harvey_three(frequency, tau_1, sigma_1, tau_2, sigma_2, tau_3, sigma_3, white_noise),
               }
    path = os.path.join(os.path.dirname(__file__), 'dicts', '%s.dict'%type)
    with open(path, 'r') as f:
        return ast.literal_eval(f.read())


def get_next(star, ext, count=1):
    """
    Get next integer
    
    When the overwriting of files is disabled, this module determines what
    the last saved file was 

    Args:
        star : target.Target
            root directory (i.e. star.params[star.name]['path']) pipeline target 
        ext : str
            name and type of file to be saved
        count : int
            starting count, which is incremented by 1 until new path is determined

    Returns:
        path : str
            unused path name


    """
    fn = '%s_%d.%s'%(ext.split('.')[0],count,ext.split('.')[-1])
    path = os.path.join(star.params[star.name]['path'],fn)
    if os.path.exists(path):
        while os.path.exists(path):
            count += 1
            fn = '%s_%d.%s'%(ext.split('.')[0],count,ext.split('.')[-1])
            path = os.path.join(star.params[star.name]['path'],fn)
    return path


def max_elements(x, y, npeaks, exp_dnu=None):
    """
    Return n max elements
    
    Module to obtain the x and y values for the n highest peaks in a power
    spectrum (or any 2D arrays really) 

    Args:
        x : numpy.ndarray
            the x values of the data
        y : numpy.ndarray
            the y values of the data
        npeaks : int
            the first n peaks
        exp_dnu : float
            if not `None`, multiplies y array by Gaussian weighting centered on `exp_dnu`

    Returns:
        peaks_x : numpy.ndarray
            the x coordinates of the first `npeaks`
        peaks_y : numpy.ndarray
            the y coordinates of the first `npeaks`


    """
    xc, yc = np.copy(x), np.copy(y)
    weights = np.ones_like(yc)
    if exp_dnu is not None:
        sig = 0.35*exp_dnu/2.35482 
        weights *= np.exp(-(xc-exp_dnu)**2./(2.*sig**2))*((sig*np.sqrt(2.*np.pi))**-1.)
    yc *= weights
    s = np.argsort(yc)
    peaks_y = y[s][-int(npeaks):][::-1]
    peaks_x = x[s][-int(npeaks):][::-1]

    return peaks_x, peaks_y


def return_max(x, y, exp_dnu=None, index=False, idx=None):
    """
    
    Return the either the value of peak or the index of the peak corresponding to the most likely dnu given a prior estimate,
    otherwise just the maximum value.

    Args:
        x : numpy.ndarray
            the independent axis (i.e. time, frequency)
        y : numpy.ndarray
            the dependent axis
        index : bool
            if true will return the index of the peak instead otherwise it will return the value. Default value is `False`.
        dnu : bool
            if true will choose the peak closest to the expected dnu `exp_dnu`. Default value is `False`.
        exp_dnu : Required[float]
            the expected dnu. Default value is `None`.

    Returns:
        result : Union[int, float]
            if `index` is `True`, result will be the index of the peak otherwise if `index` is `False` it will 
	    instead return the value of the peak.

    """

    lst = list(y)
    if lst != []:
        if exp_dnu is not None:
            lst = list(np.absolute(x-exp_dnu))
            idx = lst.index(min(lst))
        else:
            idx = lst.index(max(lst))
    if index:
        return idx
    else:
        if idx is None:
            return [], []
        return x[idx], y[idx]


def bin_data(x, y, width, log=False, mode='mean'):
    """
    Bin data
    
    Bins a series of data.

    Args:
        x : numpy.ndarray
            the x values of the data
        y : numpy.ndarray
            the y values of the data
        width : float
            bin width in muHz
        log : bool
            creates bins by using the log of the min/max values (i.e. not equally spaced in log if `True`)

    Returns:
        bin_x : numpy.ndarray
            binned frequencies
        bin_y : numpy.ndarray
            binned power
        bin_yerr : numpy.ndarray
            standard deviation of the binned y data


    """
    if log:
        mi = np.log10(min(x))
        ma = np.log10(max(x))
        no = np.int(np.ceil((ma-mi)/width))
        bins = np.logspace(mi, mi+(no+1)*width, no)
    else:
        bins = np.arange(min(x), max(x)+width, width)

    digitized = np.digitize(x, bins)
    if mode == 'mean':
        bin_x = np.array([x[digitized == i].mean() for i in range(1, len(bins)) if len(x[digitized == i]) > 0])
        bin_y = np.array([y[digitized == i].mean() for i in range(1, len(bins)) if len(x[digitized == i]) > 0])
    elif mode == 'median':
        bin_x = np.array([np.median(x[digitized == i]) for i in range(1, len(bins)) if len(x[digitized == i]) > 0])
        bin_y = np.array([np.median(y[digitized == i]) for i in range(1, len(bins)) if len(x[digitized == i]) > 0])
    else:
        pass
    bin_yerr = np.array([y[digitized == i].std()/np.sqrt(len(y[digitized == i])) for i in range(1, len(bins)) if len(x[digitized == i]) > 0])

    return bin_x, bin_y, bin_yerr


def _ask_int(question, n_trials, max_attempts=10, count=1, special=False):    
    """
    
    Asks for an integer user input

    Args:
        question : str
            the statement and/or question that needs to be answered
        range : List[float]
            if not `None`, provides a lower and/or upper bound for the selected integer
        max_attempts : int
            the maximum number of tries a user has before breaking
        count : int
            the user attempt number

    Returns:
        result : int
            the user's integer answer or `None` if the number of attempts exceeds the allowed number


    """
    while count < max_attempts:
        answer = input(question)
        try:
            if special:
                try:
                    value = float(answer)
                except ValueError:
                    print('ERROR: please try again ')
                else:
                    return value
            elif float(answer).is_integer() and not special:
                if int(answer) == 0:
                    special = True
                    question = 'What is your value for numax? '
                elif int(answer) >= 1 and int(answer) <= n_trials:
                    return int(answer)
                else:
                    print('ERROR: please select an integer between 1 and %d \n       or 0 to provide a different value\n'%n_trials)
            else:
                print("ERROR: the selection must match one of the integer values \n")
        except ValueError:
            print("ERROR: not a valid response \n")
        count += 1
    return None


def delta_nu(numax):
    """
    
    Estimates the large frequency separation using the numax scaling relation

    Args:
        numax : float
            the frequency corresponding to maximum power or numax

    Returns:
        dnu : float
            the approximated frequency spacing, dnu

    """

    return 0.22*(numax**0.797)


class Constants:
    """
    
    Container class for constants and known values -- which is
    primarily solar asteroseismic values here -- in cgs units
    
    """

    def __init__(self):
        """
        UNITS ARE IN THE SUPERIOR CGS 
        COME AT ME

        """
        # Solar values
        self.m_sun = 1.9891e33
        self.r_sun = 6.95508e10
        self.rho_sun = 1.41
        self.teff_sun = 5777.0
        self.logg_sun = 4.4
        self.teffred_sun = 8907.
        self.numax_sun = 3090.0
        self.dnu_sun = 135.1
        self.width_sun = 1300.0 
        self.tau_sun = [5.2e6,1.8e5,1.7e4,2.5e3,280.0,80.0] 
        self.tau_sun_single = [3.8e6,2.5e5,1.5e5,1.0e5,230.,70.]
        # Constants
        self.G = 6.67428e-8
        # Conversions
        self.cm2au = 6.68459e-14
        self.au2cm = 1.496e+13
        self.rad2deg = 180./np.pi
        self.deg2rad = np.pi/180.