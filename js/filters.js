// ============================================================
// FILTERING
// ============================================================

import { escapeRegex } from './ui_utils.js';
import { loadApplicationStatus } from './storage.js';

function getValue(id, fallback = '') {
    const el = document.getElementById(id);
    return el ? el.value : fallback;
}

function getChecked(id, fallback = false) {
    const el = document.getElementById(id);
    return el ? el.checked : fallback;
}

/** Read current filter values from the DOM. */
export function readFilterInputs() {
    return {
        hideRecruiters: getChecked('filter-hide-recruiters', true),
        remoteOnly: getChecked('filter-remote-only'),
        hideApplied: getChecked('filter-hide-applied'),
        title: getValue('filter-title').toLowerCase().trim(),
        company: getValue('filter-company').toLowerCase().trim(),
        location: getValue('filter-location').toLowerCase().trim(),
        salary: getValue('filter-salary-min'),
        status: getValue('filter-status'),
        ats: getValue('filter-ats'),
        skill_level: getValue('filter-skill-level'),
        experience_level: getValue('filter-experience-level'),
        country: getValue('filter-country'),
        domain: getValue('filter-domain'),
        posted: getValue('filter-posted'),
        exclude: getValue('filter-exclude').toLowerCase().trim(),
        include: getValue('filter-include').toLowerCase().trim(),
    };
}

function levenshtein(a, b) {
    const dp = Array.from({ length: a.length + 1 }, (_, i) =>
        Array.from({ length: b.length + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0))
    );
    for (let i = 1; i <= a.length; i++) {
        for (let j = 1; j <= b.length; j++) {
            dp[i][j] = a[i - 1] === b[j - 1]
                ? dp[i - 1][j - 1]
                : 1 + Math.min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1]);
        }
    }
    return dp[a.length][b.length];
}

function fuzzyMatch(search, text, threshold = 0.75) {
    if (!search) return true;
    search = search.toLowerCase();
    text = text.toLowerCase();
    if (text.includes(search)) return true;
    const words = text.split(/\W+/).filter(Boolean);
    return words.some(word => {
        const maxLen = Math.max(word.length, search.length);
        if (maxLen === 0) return false;
        const similarity = 1 - levenshtein(search, word) / maxLen;
        return similarity >= threshold;
    });
}

function jobDomains(job) {
    return Array.isArray(job.job_domain)
        ? job.job_domain.map(value => String(value).toLowerCase())
        : [];
}

/** Filter the full jobs array based on current filter inputs. */
export function filterJobs(allJobs) {
    const f = readFilterInputs();
    const apps = loadApplicationStatus();

    const titleRegex = f.title ? new RegExp(`\\b${escapeRegex(f.title)}\\b`, 'i') : null;
    const companyRegex = f.company ? new RegExp(`\\b${escapeRegex(f.company)}\\b`, 'i') : null;
    const locationRegex = f.location ? new RegExp(`\\b${escapeRegex(f.location)}\\b`, 'i') : null;

    const filterState = {
        title: f.title,
        company: f.company,
        location: f.location,
        salary: f.salary,
        remoteOnly: f.remoteOnly,
        status: f.status,
        ats: f.ats,
        skill_level: f.skill_level,
        experience_level: f.experience_level,
        country: f.country,
        domain: f.domain,
        posted: f.posted,
        exclude: f.exclude,
        include: f.include,
    };

    const filteredJobs = allJobs.filter(job => {
        // The dataset itself is Canada + entry/new-grad only. Keep this guard
        // in the frontend too so stale/old data can never leak into the UI.
        const experience = String(job.experience_level || '').toLowerCase();
        if (job.is_canada !== true) return false;
        if (!['new_grad', 'entry'].includes(experience)) return false;

        if (f.hideRecruiters && job.is_recruiter === true) return false;

        const url = job.url || job.absolute_url;
        const jobStatus = apps[url]?.status || '';
        if (f.hideApplied && (jobStatus === 'applied' || jobStatus === 'ignored')) return false;
        if (f.status && jobStatus !== f.status) return false;

        const title = (job.title || '').toLowerCase();
        const company = ((job.company || job.company_slug) || '').toLowerCase();
        let location = '';
        if (job.location) {
            location = typeof job.location === 'object'
                ? (job.location.name || '').toLowerCase()
                : String(job.location).toLowerCase();
        }

        const minSalary = parseInt(f.salary, 10) || 0;
        if (minSalary > 0) {
            const median = job.salary?.median;
            if (!median || median < minSalary) return false;
        }

        const isRemote = job.is_remote === true
            || job.remote === true
            || location.includes('remote')
            || String(job.workplaceType || '').toLowerCase() === 'remote';
        if (f.remoteOnly && !isRemote) return false;

        if (f.ats && String(job.ats || '').toLowerCase() !== f.ats.toLowerCase()) return false;

        if (f.skill_level && String(job.skill_level || '').toLowerCase() !== f.skill_level.toLowerCase()) return false;

        if (f.experience_level && String(job.experience_level || '').toLowerCase() !== f.experience_level.toLowerCase()) return false;

        if (f.country) {
            const country = String(job.location_country || '').toUpperCase();
            if (f.country === 'CA' && country !== 'CA') return false;
            if (f.country === 'US' && country !== 'US') return false;
            if (f.country === 'REMOTE' && !isRemote) return false;
            if (f.country === 'OTHER' && !['OTHER', 'UNKNOWN'].includes(country)) return false;
        }

        if (f.domain) {
            if (!jobDomains(job).includes(f.domain.toLowerCase())) return false;
        }

        if (f.posted) {
            const days = parseInt(f.posted, 10);
            const raw = job.updated_at || job.first_seen || job.scraped_at;
            const t = raw ? Date.parse(raw) : NaN;
            if (isNaN(t)) return false;
            const ageDays = (Date.now() - t) / 86400000;
            if (ageDays > days) return false;
        }

        if (f.exclude) {
            const excludeTerms = f.exclude.split(',').map(t => t.trim()).filter(Boolean);
            if (excludeTerms.some(term => title.includes(term))) return false;
        }

        if (f.include) {
            const includeTerms = f.include.split(',').map(t => t.trim()).filter(Boolean);
            if (!includeTerms.some(term => title.includes(term))) return false;
        }

        return (
            (!titleRegex || titleRegex.test(title)) &&
            (!companyRegex || companyRegex.test(company)) &&
            (!locationRegex || fuzzyMatch(f.location, location))
        );
    });

    return { filteredJobs, filterState };
}

/** Reset all filter DOM inputs to defaults. */
export function clearFilterInputs() {
    const values = {
        'filter-title': '',
        'filter-company': '',
        'filter-location': '',
        'filter-salary-min': '',
        'filter-exclude': '',
        'filter-include': '',
        'filter-status': '',
        'filter-ats': '',
        'filter-skill-level': '',
        'filter-experience-level': '',
        'filter-country': '',
        'filter-domain': '',
        'filter-posted': '',
    };
    Object.entries(values).forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    });

    const hideRecruiters = document.getElementById('filter-hide-recruiters');
    const remoteOnly = document.getElementById('filter-remote-only');
    const hideApplied = document.getElementById('filter-hide-applied');
    if (hideRecruiters) hideRecruiters.checked = true;
    if (remoteOnly) remoteOnly.checked = false;
    if (hideApplied) hideApplied.checked = false;
}
