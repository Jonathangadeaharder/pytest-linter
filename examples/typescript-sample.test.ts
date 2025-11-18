// Sample TypeScript test file for test-linter demo
import { describe, it, expect } from '@jest/globals';

describe('Sample TypeScript Tests', () => {
  it('test with setTimeout - should be flagged', async () => {
    // BAD: Time-based wait
    setTimeout(() => {
      console.log('Done waiting');
    }, 1000);

    expect(true).toBe(true);
  });

  it('test with too many assertions', () => {
    // BAD: Assertion roulette
    expect(1).toBe(1);
    expect(2).toBe(2);
    expect(3).toBe(3);
    expect(4).toBe(4);
    expect(5).toBe(5);
  });

  it('test without assertions', () => {
    // BAD: No assertions
    console.log('This test does nothing');
  });

  it('test with conditional logic', () => {
    // BAD: Test logic
    const value = Math.random();
    if (value > 0.5) {
      expect(value).toBeGreaterThan(0.5);
    } else {
      expect(value).toBeLessThan(0.5);
    }
  });

  it('good test', () => {
    // GOOD: Simple, single assertion
    const result = 2 + 2;
    expect(result).toBe(4);
  });
});
