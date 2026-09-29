// ============================================================
// JOB BOARD APP
// ============================================================

import { showToast, showLoadingToast, setUIBusy, updateFABVisibility } from './ui_utils.js';
import { saveApplicationStatus } from './storage.js';
import { createColumns } from './columns.js';
import { loadJobsProgressive } from './jobs_loader.js';
import { filterJobs, clearFilterInputs } from './filters.js';
import { render } from './renderer.js';
import { updateURL, loadFromURL } from './url_state.js';
import { setupEventListeners } from './events.js';
import { sortJobs } from './sort_logic.js';
import { toggleView, updateHeatmapIfVisible } from './map_view.js';

class JobBoardApp {
    constructor() {
        this.allJobs = [];
        this.filteredJobs = [];
        this.currentPage = 1;
        this.virtualFilteredCount = 0;
        this.perPage = window.innerWidth <= 900 ? 25 : 50;
        this.sortState = { key: null, direction: 'asc' };

        this.isSorting = false;
        this.isFullyLoaded = false;

        this.filterState = {
            title: '',
            company: '',
            location: '',
            salary: '',
            status: '',
            ats: '',
            skill_level: '',
            experience_level: '',
            country: 'CA',
            domain: '',
            posted: '',
            exclude: '',
            include: '',
            remoteOnly: false,
            hideRecruiters: true,
            hideApplied: false
        };

        this.debounceTimer = null;
        this.columns = createColumns();
        this.sortWorker = null;
    }

    async init() {
        await this.loadJobs();
        setupEventListeners(this);
        this.loadFromURL();
        this.setupViewToggle();
        this.render();
    }

    async loadJobs() {
        const loadingEl = document.getElementById('loading');
        const resultsEl = document.getElementById('results');

        try {
            await loadJobsProgressive(this);
            this.sortState = { key: null, direction: 'asc' };

            loadingEl.style.display = 'none';
            resultsEl.style.display = 'block';

            console.log(`Loaded ${this.allJobs.length} jobs (more loading...)`);
        } catch (error) {
            console.error('Error loading jobs:', error);
            showToast('Error loading job data.', 'danger');
            loadingEl.textContent = 'Failed to load job data.';
        }
    }

    render() {
        render(this);
    }

    debounceRender() {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.render(), 300);
    }

    applyFilters() {
        const { filteredJobs, filterState } = filterJobs(this.allJobs);
        this.filteredJobs = filteredJobs;
        this.filterState = filterState;
        this.currentPage = 1;
        this.sortedJobs = null;
        updateURL(this.filterState, this.currentPage, this.sortState);
        updateHeatmapIfVisible();

        const sortableKeys = ['company', 'salary', 'posted'];
        if (this.sortState.key && sortableKeys.includes(this.sortState.key)) {
            this.sortAndRender();
        } else {
            this.sortState.key = null;
            this.render();
        }
    }

    clearFilters() {
        clearFilterInputs();
        this.filterState = {
            title: '', company: '', location: '', salary: '', status: '',
            ats: '', skill_level: '', experience_level: '', country: 'CA', domain: '',
            posted: '', exclude: '', include: '', remoteOnly: false,
            hideRecruiters: true, hideApplied: false
        };
        this.filteredJobs = [...this.allJobs];
        this.currentPage = 1;
        this.sortedJobs = null;
        updateURL(this.filterState, this.currentPage, this.sortState);
        updateHeatmapIfVisible();

        const sortableKeys = ['company', 'salary', 'posted'];
        if (this.sortState.key && sortableKeys.includes(this.sortState.key)) {
            this.sortAndRender();
        } else {
            this.render();
        }
    }

    refilter() {
        const { filteredJobs, filterState } = filterJobs(this.allJobs);
        this.filteredJobs = filteredJobs;
        this.filterState = filterState;
        updateHeatmapIfVisible();
        this.render();
    }

    hasActiveFilters() {
        const f = this.filterState;
        return f.title || f.company || f.location || f.salary || f.status ||
            f.ats || f.skill_level || f.experience_level || f.country || f.domain ||
            f.posted || f.remoteOnly || f.exclude || f.include;
    }

    handleSort(key) {
        if (!this.isFullyLoaded) {
            showToast('Please wait until dataset processing finishes...', 'warning');
            return;
        }
        if (this.isSorting) return;

        if (this.sortState.key === key) {
            this.sortState.direction = this.sortState.direction === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortState.key = key;
            this.sortState.direction = 'asc';
        }

        this.currentPage = 1;
        updateURL(this.filterState, this.currentPage, this.sortState);
        this.sortAndRender();
    }

    sortAndRender() {
        if (!this.sortWorker) {
            this.sortOnMainThread();
            return;
        }
        this.isSorting = true;
        this.sortLoader = showLoadingToast('Sorting records...');
        this.sortWorker.postMessage({
            type: 'SORT',
            jobsToSort: this.filteredJobs,
            sortState: this.sortState,
        });
    }

    sortOnMainThread() {
        this.sortedJobs = sortJobs([...this.filteredJobs], this.sortState);
        this.virtualFilteredCount = this.sortedJobs.length;
        this.currentPage = 1;
        this.render();
    }

    previousPage() {
        if (this.currentPage > 1) {
            this.currentPage--;
            this.triggerPageUpdate();
        }
    }

    getTotalJobsCount() {
        if (!this.isFullyLoaded) return this.filteredJobs.length;
        if (this.sortState?.key && this.sortedJobs) return this.sortedJobs.length;
        return this.filteredJobs.length;
    }

    nextPage() {
        const totalJobsCount = this.getTotalJobsCount();
        const totalPages = Math.max(1, Math.ceil(totalJobsCount / this.perPage));
        if (this.currentPage < totalPages) {
            this.currentPage++;
            this.triggerPageUpdate();
        }
    }

    triggerPageUpdate() {
        window.scrollTo(0, 0);
        this.render();
    }

    loadFromURL() {
        const { hasFilters, page, sortKey, sortDir } = loadFromURL();
        this.currentPage = page;
        if (sortKey) this.sortState = { key: sortKey, direction: sortDir };
        if (hasFilters) this.applyFilters();
    }

    handleBatch() {
        const selected = document.querySelectorAll('.save-checkbox:checked, .apply-checkbox:checked, .ignored-checkbox:checked');
        if (selected.length === 0) {
            showToast('Please select at least one job first.', 'warning');
            return;
        }

        setUIBusy(true);
        try {
            document.querySelectorAll('.save-checkbox:checked').forEach(box => {
                if (box.dataset.jobUrl) saveApplicationStatus(box.dataset.jobUrl, 'saved');
            });
            document.querySelectorAll('.apply-checkbox:checked').forEach(box => {
                if (box.dataset.jobUrl) saveApplicationStatus(box.dataset.jobUrl, 'applied');
            });
            document.querySelectorAll('.ignored-checkbox:checked').forEach(box => {
                if (box.dataset.jobUrl) saveApplicationStatus(box.dataset.jobUrl, 'ignored');
            });

            showToast(`Updated ${selected.length} job(s) successfully!`, 'success');
            updateFABVisibility();
            this.render();
        } catch (err) {
            showToast('Error updating job status.', 'danger');
            console.error(err);
        } finally {
            setUIBusy(false);
        }
    }

    setupViewToggle() {
        document.querySelectorAll('.view-toggle').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.view-toggle').forEach(b => {
                    b.classList.remove('active', 'btn-primary');
                    b.classList.add('btn-outline-primary');
                });
                btn.classList.add('active', 'btn-primary');
                btn.classList.remove('btn-outline-primary');
                toggleView(btn.dataset.view, this);
            });
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const app = new JobBoardApp();
    window.app = app;
    app.init();
});
