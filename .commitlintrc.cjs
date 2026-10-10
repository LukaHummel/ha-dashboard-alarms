module.exports = {
  extends: ['@commitlint/config-conventional'],
  defaultIgnores: false,
  // Only Git-generated merge/revert commits are exempt; PR titles never are.
  ignores: [message => process.env.COMMITLINT_PR_TITLE !== 'true' && (
    /^Merge (?:branch|pull request|remote-tracking branch|tag) /.test(message)
    || /^Revert "[^\n]+"\r?\n\r?\nThis reverts commit [0-9a-f]{40}[.,]/.test(message)
  )],
  rules: {
    // Match Release Please's structure without imposing prose formatting rules.
    'subject-case': [0],
    'subject-full-stop': [0],
    'header-max-length': [0],
    'body-max-line-length': [0],
    'footer-max-line-length': [0],
    'body-leading-blank': [2, 'always'],
    'footer-leading-blank': [2, 'always'],
    'type-enum': [2, 'always', [
      'build', 'chore', 'ci', 'deps', 'docs', 'feat', 'fix',
      'perf', 'refactor', 'revert', 'style', 'test',
    ]],
  },
};
