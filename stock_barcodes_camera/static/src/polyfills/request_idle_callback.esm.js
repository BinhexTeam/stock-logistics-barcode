/** @odoo-module **/

// Polyfill for Safari / older browsers
if (typeof window !== "undefined" && !window.requestIdleCallback) {
    window.requestIdleCallback = function (cb, options) {
        const start = Date.now();
        const timeout = (options && options.timeout) || 1;
        return window.setTimeout(function () {
            cb({
                didTimeout: false,
                timeRemaining: function () {
                    return Math.max(0, timeout - (Date.now() - start));
                },
            });
        }, 1);
    };
}

if (typeof window !== "undefined" && !window.cancelIdleCallback) {
    window.cancelIdleCallback = function (id) {
        clearTimeout(id);
    };
}
