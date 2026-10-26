/** Comments on one video (SPEC §8.11, Tier 2): newest first, ≤ 300 characters,
 * delete your own, report anyone else's. Three reports hide a comment. */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { date, initials } from '../lib/format';
import type { CommentItem } from '../lib/types';
import { BottomSheet } from './common';
import { Icon } from './Icon';

const MAX = 300;

function timeAgo(dateString: string): string {
  try {
    const d = new Date(dateString);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (diffSec < 45) return 'Just now';
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date(dateString);
  } catch {
    return date(dateString);
  }
}

export function CommentsSheet({ mediaId, onClose }: { mediaId: number; onClose: () => void }) {
  const { me, toast } = useApp();
  const [comments, setComments] = useState<CommentItem[] | null>(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .comments(mediaId)
      .then((response) => !cancelled && setComments(response.comments))
      .catch(() => !cancelled && setComments([]));
    return () => {
      cancelled = true;
    };
  }, [mediaId]);

  function fail(error: unknown) {
    toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad');
  }

  async function post() {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    try {
      const comment = await api.addComment(mediaId, trimmed);
      setComments((list) => [comment, ...(list ?? [])]);
      setText('');
      toast('Comment posted', 'plain');
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    try {
      await api.deleteComment(id);
      setComments((list) => (list ?? []).filter((c) => c.id !== id));
      toast('Comment deleted', 'plain');
    } catch (error) {
      fail(error);
    }
  }

  async function report(id: number) {
    try {
      const result = await api.report('comment', id, 'offensive');
      if (result.hidden) setComments((list) => (list ?? []).filter((c) => c.id !== id));
      toast('Reported. Thank you.', 'plain');
    } catch (error) {
      fail(error);
    }
  }

  const count = comments?.length ?? 0;

  return (
    <BottomSheet open onClose={onClose} className="comments-sheet">
      <div className="cm-header">
        <div className="cm-title-wrap">
          <h3 className="cm-title">Comments</h3>
          {comments !== null && (
            <span className="cm-count-badge">{count}</span>
          )}
        </div>
        <button
          type="button"
          className="sheet-close-btn"
          onClick={onClose}
          aria-label="Close comments"
        >
          <Icon name="i-x" size={16} />
        </button>
      </div>

      <div className="cm-content-area">
        {comments === null ? (
          <div className="cm-loading">
            {[1, 2, 3].map((n) => (
              <div key={n} className="cm-skeleton">
                <div className="cm-skel-av" />
                <div className="cm-skel-body">
                  <div className="cm-skel-line skel-short" />
                  <div className="cm-skel-line skel-long" />
                </div>
              </div>
            ))}
          </div>
        ) : comments.length === 0 ? (
          <div className="cm-empty">
            <div className="cm-empty-bubble">
              <Icon name="i-comment" size={28} />
            </div>
            <h4 className="cm-empty-title">No comments yet</h4>
            <p className="cm-empty-text">
              Been here or planning to go? Share your thoughts, tips, or questions!
            </p>
          </div>
        ) : (
          <ul className="cm-list">
            {comments.map((c) => {
              const isMine = Boolean(c.mine || (me && me.username === c.user.username));
              return (
                <li key={c.id} className="cm-card">
                  <Link
                    to={`/u/${c.user.username}`}
                    onClick={onClose}
                    className="cm-av-link"
                    aria-label={`Open @${c.user.username}'s profile`}
                  >
                    <span className="avatar cm-avatar">
                      {initials(c.user.display_name || c.user.username)}
                    </span>
                  </Link>

                  <div className="cm-card-main">
                    <div className="cm-card-head">
                      <Link
                        to={`/u/${c.user.username}`}
                        onClick={onClose}
                        className="cm-user-link"
                      >
                        <span className="cm-name">
                          {c.user.display_name || c.user.username}
                        </span>
                        <span className="cm-handle">@{c.user.username}</span>
                      </Link>
                      {isMine && <span className="cm-you-pill">You</span>}
                      <span className="cm-time">{timeAgo(c.at)}</span>
                    </div>

                    <p className="cm-card-text">{c.text}</p>

                    <div className="cm-card-foot">
                      {isMine ? (
                        <button
                          type="button"
                          className="cm-action-btn cm-delete-btn"
                          onClick={() => void remove(c.id)}
                          aria-label="Delete comment"
                        >
                          <Icon name="i-trash" size={13} />
                          <span>Delete</span>
                        </button>
                      ) : (
                        me && (
                          <button
                            type="button"
                            className="cm-action-btn cm-report-btn"
                            onClick={() => void report(c.id)}
                            aria-label="Report comment"
                          >
                            <Icon name="i-flag" size={13} />
                            <span>Report</span>
                          </button>
                        )
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {me ? (
        <form
          className="cm-composer"
          onSubmit={(event) => {
            event.preventDefault();
            void post();
          }}
        >
          <div className="cm-composer-row">
            <span className="avatar cm-composer-av">
              {initials(me.display_name || me.username)}
            </span>
            <div className="cm-input-shell">
              <input
                id="comment-text"
                type="text"
                maxLength={MAX}
                value={text}
                placeholder="Add a comment..."
                autoComplete="off"
                onChange={(event) => setText(event.target.value)}
              />
              {text.length > 0 && (
                <span className="cm-char-counter">
                  {text.length}/{MAX}
                </span>
              )}
            </div>
            <button
              type="submit"
              className={`cm-send-btn ${text.trim() ? 'active' : ''}`}
              disabled={busy || !text.trim()}
              aria-label="Post comment"
            >
              <Icon name="i-nav" size={16} />
            </button>
          </div>
        </form>
      ) : (
        <div className="cm-guest-bar">
          <span>Sign in to join the discussion</span>
          <Link to="/signin" className="btn btn-xs btn-primary" onClick={onClose}>
            Sign in
          </Link>
        </div>
      )}
    </BottomSheet>
  );
}
