import React, { useState, useCallback, useEffect } from 'react';
import { PageConfig } from '@jupyterlab/coreutils';
import { createUseStyles } from 'react-jss';
import { getEnvVariable, testZenodoConnection } from '../API/API_functions';


const useStyles = createUseStyles({
    root: {
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#fff',
    },
    loginContainer: {
        backgroundColor: '#fff',
        padding: '20px',
        borderRadius: '8px',
        boxShadow: '0 0 10px rgba(0, 0, 0, 0.1)',
        width: '300px',
        textAlign: 'center',
        verticalAlign: 'top'
    },
    formGroup: {
        marginBottom: '20px',
    },
    input: {
        width: 'calc(100% - 20px)', // Change to a string to avoid type errors
        padding: '10px',
        border: '1px solid #ccc',
        borderRadius: '4px',
        margin: '10px 0',
    },
    button: {
        width: '100%',
        padding: '10px',
        backgroundColor: '#4CAF50',
        color: 'white',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        transition: 'background-color 0.3s',
        '&:hover': {
            backgroundColor: '#45a049',
        },
    },
    checkboxContainer: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: '10px',
        flexDirection: 'row',
    },
    checkboxLabel: {
        display: 'flex',
        alignItems: 'center',
    },
    checkboxInput: {
        marginRight: '5px',
    },
});

const Login: React.FC = () => {
    const classes = useStyles();
    const [connectionStatus, setConnectionStatus] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isSandbox, setIsSandbox] = useState<boolean>(true); // default sandbox true
    const [envSandboxLoaded, setEnvSandboxLoaded] = useState(false);

    // Load sandbox flag from server env (if present) once
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const env = await getEnvVariable('ZENODO_SANDBOX');
                if (!cancelled && env && typeof env === 'object' && 'ZENODO_SANDBOX' in env) {
                    const val = String((env as any)['ZENODO_SANDBOX']).toLowerCase();
                    setIsSandbox(val === 'true' || val === '1');
                }
            } catch (e) {
                // ignore
            } finally {
                if (!cancelled) setEnvSandboxLoaded(true);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const handleCheckboxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const checked = event.target.checked;
        setIsSandbox(checked);
        // Persist preference locally for user experience (does not flip server env automatically)
        try { window.localStorage.setItem('zenodo_sandbox_pref', checked ? 'true' : 'false'); } catch { /* ignore */ }
    };

    const oauthLogin = useCallback(() => {
        // Detect if running via JupyterHub or standalone JupyterLab
        const hubPrefix = PageConfig.getOption('hubPrefix') || '';
        const baseUrl = PageConfig.getOption('baseUrl') || '/';

        console.log('OAuth Login Debug:', { hubPrefix, baseUrl });

        // If hubPrefix exists and is not just '/', we're in a Hub context
        const isHub = hubPrefix && hubPrefix !== '/' && hubPrefix !== '';

        console.log('isHub:', isHub);

        if (isHub) {
            // JupyterHub: handlers are registered on the Hub
            console.log('Redirecting to Hub path:', hubPrefix + 'zenodo/login');
            window.location.href = hubPrefix + 'zenodo/login';
        } else {
            // Standalone JupyterLab: handlers are registered on the single-user server
            console.log('Redirecting to standalone path:', baseUrl + 'zenodo-jupyterlab/oauth/login');
            window.location.href = baseUrl + 'zenodo-jupyterlab/oauth/login';
        }
    }, []);

    const testAPIConnection = async () => {
        setIsLoading(true);
        try {
            const response: any = await testZenodoConnection();
            if (response && Number(response['status']) === 200) {
                setConnectionStatus('Zenodo API reachable');
            } else {
                setConnectionStatus('Zenodo API not reachable \n (login may be required)');
            }
        } catch (e) {
            setConnectionStatus('Zenodo API check failed');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        // After potential redirect back, try connection test
        testAPIConnection();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <div className={classes.root}>
            <div className={classes.loginContainer}>
                <h2>Zenodo Login</h2>
                <div className={classes.formGroup}>
                    <div className={classes.checkboxContainer}>
                        <label className={classes.checkboxLabel}>
                            <input
                                type="checkbox"
                                checked={isSandbox}
                                onChange={handleCheckboxChange}
                                className={classes.checkboxInput}
                            />
                            Use Sandbox
                        </label>
                    </div>
                    <button className={classes.button} onClick={oauthLogin}>Login with Zenodo</button>
                </div>
                {isLoading ? (
                    <p>Checking connection...</p>
                ) : connectionStatus ? (
                    <div>
                        <h3>Connection Status</h3>
                        <p>{connectionStatus}</p>
                    </div>
                ) : (
                    <p>Ready to initiate OAuth login.</p>
                )}
                {!envSandboxLoaded && <p>Loading environment...</p>}
            </div>
        </div>
    );
};

export default Login;

