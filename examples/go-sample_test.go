package example

import (
	"os"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// Good: Simple test with one assertion
func TestAddition(t *testing.T) {
	result := 2 + 2
	assert.Equal(t, 4, result)
}

// BAD: Test with time.Sleep
func TestWithSleep(t *testing.T) {
	// Time-based wait - should be flagged
	time.Sleep(1 * time.Second)
	assert.True(t, true)
}

// BAD: Test with too many assertions
func TestTooManyAssertions(t *testing.T) {
	assert.Equal(t, 1, 1)
	assert.Equal(t, 2, 2)
	assert.Equal(t, 3, 3)
	assert.Equal(t, 4, 4)
	assert.Equal(t, 5, 5)
}

// BAD: Test without assertions
func TestNoAssertions(t *testing.T) {
	// This test does nothing
	_ = 2 + 2
}

// BAD: Test with conditional logic
func TestWithLogic(t *testing.T) {
	value := 10
	if value > 5 {
		assert.True(t, true)
	} else {
		assert.False(t, false)
	}
}

// GOOD: Table-driven test (parametrized)
func TestTableDriven(t *testing.T) {
	tests := []struct {
		name     string
		input    int
		expected int
	}{
		{"positive", 5, 5},
		{"negative", -5, -5},
		{"zero", 0, 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			assert.Equal(t, tt.expected, tt.input)
		})
	}
}

// BAD: Test with file I/O without proper setup
func TestFileIO(t *testing.T) {
	// Mystery Guest - file I/O without fixture
	data, err := os.ReadFile("test.txt")
	assert.NoError(t, err)
	assert.NotNil(t, data)
}

// Setup function
func TestMain(m *testing.M) {
	// Setup code here
	code := m.Run()
	// Teardown code here
	os.Exit(code)
}
